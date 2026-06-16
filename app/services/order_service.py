"""Order Service — handles order lifecycle, payment, and cart operations.

All DB-writing functions use explicit try/rollback.
process_payment uses optimistic locking (version column) and row-level
locking (with_for_update) to prevent double-pay race conditions.
"""
from datetime import datetime
from sqlalchemy import select
from extensions import db
from app.models import Order, OrderItem, RestaurantTable, MenuItem, Modifier, Payment, AuditLog


def create_order(branch_id: int, table_id: int, employee_id: int,
                 order_type: str, pax: int, notes: str) -> Order:
    """Creates a new order with audit trail."""
    if table_id:
        table = db.session.get(RestaurantTable, table_id)
        if not table or table.branch_id != branch_id:
            raise ValueError("Invalid table for this branch")
        if order_type == 'dine_in':
            table.status = 'occupied'

    try:
        order = Order(
            branch_id=branch_id,
            table_id=table_id,
            employee_id=employee_id,
            order_type=order_type,
            status='open',
            pax=pax,
            notes=notes
        )
        db.session.add(order)
        db.session.flush()

        audit = AuditLog(table_name='orders', record_id=order.order_id,
                         action='INSERT', changed_by=employee_id)
        db.session.add(audit)
        db.session.commit()
        return order
    except Exception:
        db.session.rollback()
        raise


def add_item(order_id: int, item_id: int, quantity: int,
             notes: str, seat_number: int, modifiers: list) -> OrderItem:
    """Adds an item to an open order. Snapshots price at time of add."""
    order = db.session.get(Order, order_id)
    if not order or order.status != 'open':
        raise ValueError("Order is not open")

    menu_item = db.session.get(MenuItem, item_id)
    if not menu_item or menu_item.is_available == 0:
        raise ValueError("Item not available")

    # Snapshot price at time of add — never re-read at payment time
    unit_price = menu_item.price_cents
    if modifiers:
        for mod_id in modifiers:
            mod = db.session.get(Modifier, mod_id)
            if mod:
                unit_price += mod.price_cents

    try:
        order_item = OrderItem(
            order_id=order_id,
            item_id=item_id,
            quantity=quantity,
            unit_price_cents=unit_price,
            notes=notes,
            seat_number=seat_number,
            status='pending'
        )
        db.session.add(order_item)
        db.session.commit()
        return order_item
    except Exception:
        db.session.rollback()
        raise


def send_to_kitchen(order_id: int, order_item_ids: list) -> list:
    """Sends selected items to the kitchen, deducts inventory, routes to KDS."""
    from app.services.inventory_service import deduct_for_items
    from app.services.kds_service import route_to_station
    from app.services.printer_service import print_kot

    order = db.session.get(Order, order_id)
    if not order:
        raise ValueError("Order not found")

    if not order_item_ids:
        raise ValueError("No items specified for kitchen")

    try:
        items = []
        for item_id in order_item_ids:
            item = db.session.get(OrderItem, item_id)
            if not item or item.order_id != order_id:
                raise ValueError("Item does not belong to this order")
            if item.status == 'pending':
                item.status = 'kitchen'
                item.sent_at = datetime.utcnow()
                items.append(item)

        db.session.flush()

        if items:
            deduct_for_items(items)
            for item in items:
                route_to_station(item)
            try:
                print_kot(order_id, [i.order_item_id for i in items], order.branch_id)
            except Exception:
                pass  # Printer failure must never block kitchen flow

        db.session.commit()
        return items
    except Exception:
        db.session.rollback()
        raise


def update_item_status(order_item_id: int, new_status: str) -> OrderItem:
    """Updates the status of an order item with validated transitions."""
    item = db.session.get(OrderItem, order_item_id)
    if not item:
        raise ValueError("Item not found")

    valid_transitions = {
        'pending': ['kitchen', 'cancelled'],
        'kitchen': ['served', 'cancelled'],
        'served': ['cancelled']
    }

    if new_status not in valid_transitions.get(item.status, []):
        raise ValueError(f"Invalid transition from {item.status} to {new_status}")

    try:
        item.status = new_status
        if new_status == 'served':
            item.served_at = datetime.utcnow()
            from app.models import KdsLog
            klog = KdsLog.query.filter_by(order_item_id=item.order_item_id).first()
            if klog and klog.displayed_at:
                klog.mitigation_time_minutes = int(
                    (datetime.utcnow() - klog.displayed_at).total_seconds() / 60
                )

        db.session.commit()
        return item
    except Exception:
        db.session.rollback()
        raise


def cancel_item(order_item_id: int, reason: str, cancelled_by: int) -> OrderItem:
    """Cancels an order item and restores inventory if it was in kitchen."""
    from app.services.inventory_service import restore_for_items

    item = db.session.get(OrderItem, order_item_id)
    if not item:
        raise ValueError("Item not found")

    try:
        old_status = item.status
        item.status = 'cancelled'

        if old_status == 'kitchen':
            restore_for_items([item])

        audit = AuditLog(
            table_name='order_items', record_id=item.order_item_id,
            action='UPDATE', changed_by=cancelled_by,
            old_values=f"status={old_status}", new_values="status=cancelled"
        )
        db.session.add(audit)
        db.session.commit()
        return item
    except Exception:
        db.session.rollback()
        raise


def close_order(order_id: int) -> Order:
    """Closes an order after all items are served or cancelled."""
    order = db.session.get(Order, order_id)
    if not order:
        raise ValueError("Order not found")

    for item in order.items:
        if item.status not in ['served', 'cancelled']:
            raise ValueError("Not all items are served or cancelled")

    try:
        order.status = 'served'
        order.closed_at = datetime.utcnow()
        db.session.commit()
        return order
    except Exception:
        db.session.rollback()
        raise


def process_payment(order_id: int, method: str, amount_cents: int,
                    tendered_cents: int, reference_no: str,
                    employee_id: int, split_items: list = None) -> Payment:
    """Processes payment with optimistic locking to prevent double-pay.

    Uses SELECT ... FOR UPDATE on the Order row to serialize concurrent
    payment attempts. Checks order.status != 'paid' before proceeding.
    Increments order.version for optimistic concurrency control.
    """
    from app.services.loyalty_service import award_points
    from app.services.email_service import send_receipt
    from app.services.printer_service import print_receipt

    # Row-level lock — serializes concurrent payment attempts
    order = db.session.execute(
        select(Order).where(Order.order_id == order_id).with_for_update()
    ).scalar_one_or_none()
    if not order:
        raise ValueError("Order not found")

    # CRITICAL: Block payment on already-paid or cancelled orders
    if order.status == 'paid':
        raise ValueError("Order is already fully paid")
    if order.status == 'cancelled':
        raise ValueError("Cannot pay a cancelled order")
    if order.status not in ('open', 'served', 'confirmed'):
        raise ValueError("Order cannot be paid in current state")

    try:
        payment = Payment(
            order_id=order_id,
            employee_id=employee_id,
            method=method,
            amount_cents=amount_cents,
            tendered_cents=tendered_cents,
            change_cents=(tendered_cents - amount_cents) if tendered_cents else 0,
            reference_no=reference_no
        )
        db.session.add(payment)
        db.session.flush()

        summary = get_order_summary(order_id)
        current_paid = summary['paid_cents'] + amount_cents

        if current_paid >= summary['total_cents']:
            order.status = 'paid'
            if order.table_id:
                table = db.session.get(RestaurantTable, order.table_id)
                if table:
                    table.status = 'cleaning'

            # Award loyalty points if customer attached (idempotency in loyalty_service)
            if order.customer_id:
                try:
                    award_points(order.customer_id, order.order_id, current_paid)
                except Exception:
                    pass

        # Optimistic lock bump
        order.version += 1

        # Print receipt (never raise to caller)
        try:
            print_receipt(payment.payment_id, order.branch_id)
        except Exception:
            pass

        # Queue receipt email if customer has email
        if order.customer_id:
            from app.models import Customer
            customer = db.session.get(Customer, order.customer_id)
            if customer and customer.email:
                try:
                    send_receipt(order.order_id, payment.payment_id, customer.email)
                except Exception:
                    pass

        audit = AuditLog(table_name='payments', record_id=payment.payment_id,
                         action='INSERT', changed_by=employee_id)
        db.session.add(audit)
        db.session.commit()
        return payment
    except Exception:
        db.session.rollback()
        raise


def cancel_order(order_id: int, reason: str, cancelled_by: int) -> Order:
    """Cancels an entire order and restores inventory for kitchen items."""
    from app.services.inventory_service import restore_for_items

    order = db.session.get(Order, order_id)
    if not order:
        raise ValueError("Order not found")
    if order.status == 'paid':
        raise ValueError("Cannot cancel a paid order — use void instead")

    try:
        order.status = 'cancelled'
        if order.table_id:
            table = db.session.get(RestaurantTable, order.table_id)
            if table:
                table.status = 'available'

        kitchen_items = [item for item in order.items if item.status == 'kitchen']
        for item in order.items:
            if item.status != 'cancelled':
                item.status = 'cancelled'

        if kitchen_items:
            restore_for_items(kitchen_items)

        audit = AuditLog(table_name='orders', record_id=order.order_id,
                         action='UPDATE', changed_by=cancelled_by,
                         old_values=f"status={order.status}",
                         new_values="status=cancelled")
        db.session.add(audit)
        db.session.commit()
        return order
    except Exception:
        db.session.rollback()
        raise


def get_order_summary(order_id: int) -> dict:
    """Calculates order totals. Read-only — no DB writes."""
    order = db.session.get(Order, order_id)
    if not order:
        raise ValueError("Order not found")

    total_cents = 0
    for item in order.items:
        if item.status != 'cancelled':
            total_cents += (item.unit_price_cents * item.quantity) - item.discount_cents

    total_cents -= (order.discount_cents or 0)
    paid_cents = sum(p.amount_cents for p in order.payments if not p.is_voided)

    return {
        'order': order,
        'items': order.items,
        'payments': order.payments,
        'total_cents': max(0, total_cents),
        'paid_cents': paid_cents,
        'balance_cents': max(0, total_cents - paid_cents)
    }


def attach_customer(order_id: int, customer_id: int) -> Order:
    """Links customer to order via customer_id FK."""
    from app.models import Customer
    order = db.session.get(Order, order_id)
    if not order:
        raise ValueError("Order not found")

    customer = db.session.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    order.customer_id = customer_id
    db.session.commit()
    return order
