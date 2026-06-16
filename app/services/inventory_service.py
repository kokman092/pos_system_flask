"""Inventory Service — handles stock deduction, replenishment, waste, and counting.

FIFO batch deduction uses with_for_update() to prevent concurrent overdraw.
All DB-writing functions use explicit try/rollback.
"""
from extensions import db
from app.models import (
    OrderItem, ItemIngredient, StockBatch, Ingredient,
    WasteLog, InventoryCountSession, InventoryCountItem, MenuItem,
    Supplier, PurchaseOrder, PurchaseOrderItem, SupplierPriceHistory
)


def deduct_for_items(order_items: list) -> None:
    """Deducts ingredients from stock using FIFO batch deduction.

    Uses row-level locking on StockBatch rows to prevent concurrent
    orders from overdrowing the same batch.
    """
    from app.services.email_service import send_low_stock_alert
    from decimal import Decimal

    for item in order_items:
        recipes = ItemIngredient.query.filter_by(item_id=item.item_id).all()
        for recipe in recipes:
            qty_needed = float(recipe.qty_used) * item.quantity
            ingredient = db.session.get(Ingredient, recipe.ingredient_id)

            if ingredient:
                # Lock batches for atomic FIFO deduction
                batches = (StockBatch.query
                           .filter_by(ingredient_id=ingredient.ingredient_id)
                           .filter(StockBatch.qty_remaining > 0)
                           .order_by(StockBatch.received_at)
                           .with_for_update()
                           .all())

                for batch in batches:
                    if qty_needed <= 0:
                        break
                    available = float(batch.qty_remaining)
                    if available >= qty_needed:
                        batch.qty_remaining = Decimal(str(batch.qty_remaining or 0)) - Decimal(str(qty_needed))
                        qty_needed = 0
                    else:
                        batch.qty_remaining = 0
                        qty_needed -= available

                ingredient.qty_in_stock = Decimal(str(ingredient.qty_in_stock or 0)) - Decimal(str(float(recipe.qty_used) * item.quantity))

                if float(ingredient.qty_in_stock) < float(ingredient.reorder_level):
                    try:
                        send_low_stock_alert(ingredient.name, ingredient.qty_in_stock, ingredient.branch_id)
                    except Exception:
                        pass  # Alert failure must never block order flow
                if float(ingredient.qty_in_stock) <= 0:
                    mi = db.session.get(MenuItem, item.item_id)
                    if mi:
                        mi.is_available = 0


    # Commit handled by caller (send_to_kitchen wraps in transaction)


def restore_for_items(order_items: list) -> None:
    """Restores inventory when items are cancelled."""
    from decimal import Decimal
    for item in order_items:
        recipes = ItemIngredient.query.filter_by(item_id=item.item_id).all()
        for recipe in recipes:
            qty_to_restore = float(recipe.qty_used) * item.quantity
            ingredient = db.session.get(Ingredient, recipe.ingredient_id)
            if ingredient:
                ingredient.qty_in_stock = Decimal(str(ingredient.qty_in_stock or 0)) + Decimal(str(qty_to_restore))
                batch = (StockBatch.query
                         .filter_by(ingredient_id=ingredient.ingredient_id)
                         .order_by(StockBatch.received_at.desc())
                         .first())
                if batch:
                    batch.qty_remaining = Decimal(str(batch.qty_remaining or 0)) + Decimal(str(qty_to_restore))


    # Commit handled by caller


def add_stock_batch(ingredient_id: int, qty_received: float,
                    cost_per_unit_cents: int, expiry_date,
                    supplier_ref: str, branch_id: int, notes: str = None) -> StockBatch:
    """Adds a new stock batch and updates ingredient qty_in_stock."""
    from decimal import Decimal
    ingredient = db.session.get(Ingredient, ingredient_id)
    if not ingredient:
        raise ValueError("Ingredient not found")
    if ingredient.branch_id != branch_id:
        raise PermissionError("Ingredient does not belong to this branch")

    try:
        batch = StockBatch(
            ingredient_id=ingredient_id,
            qty_received=qty_received,
            qty_remaining=qty_received,
            cost_per_unit_cents=cost_per_unit_cents,
            expiry_date=expiry_date,
            supplier_ref=supplier_ref,
            notes=notes
        )
        db.session.add(batch)
        ingredient.qty_in_stock = Decimal(str(ingredient.qty_in_stock or 0)) + Decimal(str(qty_received))
        db.session.commit()
        return batch

    except Exception:
        db.session.rollback()
        raise


def adjust_stock(ingredient_id: int, new_qty: float,
                 adjusted_by: int, reason: str) -> Ingredient:
    """Manually adjusts stock levels with audit trail."""
    from app.models import AuditLog

    ingredient = db.session.get(Ingredient, ingredient_id)
    if not ingredient:
        raise ValueError("Ingredient not found")

    try:
        old_qty = float(ingredient.qty_in_stock)
        ingredient.qty_in_stock = new_qty

        audit = AuditLog(
            table_name='ingredients', record_id=ingredient_id,
            action='UPDATE', changed_by=adjusted_by,
            old_values=f"qty_in_stock={old_qty}",
            new_values=f"qty_in_stock={new_qty}, reason={reason}"
        )
        db.session.add(audit)
        db.session.commit()
        return ingredient
    except Exception:
        db.session.rollback()
        raise


def log_waste(ingredient_id: int, qty: float, reason: str,
              recorded_by: int, branch_id: int) -> WasteLog:
    """Logs wasted ingredients and deducts from stock using FIFO."""
    from decimal import Decimal
    ingredient = db.session.get(Ingredient, ingredient_id)
    if not ingredient:
        raise ValueError("Ingredient not found")
    if ingredient.branch_id != branch_id:
        raise PermissionError("Ingredient does not belong to this branch")

    try:
        waste = WasteLog(
            branch_id=branch_id,
            ingredient_id=ingredient_id,
            qty=qty,
            reason=reason,
            recorded_by=recorded_by,
            unit_cost_cents=ingredient.cost_per_unit_cents
        )
        db.session.add(waste)

        ingredient.qty_in_stock = Decimal(str(ingredient.qty_in_stock or 0)) - Decimal(str(qty))
        batches = (StockBatch.query
                   .filter_by(ingredient_id=ingredient.ingredient_id)
                   .filter(StockBatch.qty_remaining > 0)
                   .order_by(StockBatch.received_at)
                   .all())
        qty_needed = qty
        for batch in batches:
            if qty_needed <= 0:
                break
            available = float(batch.qty_remaining)
            if available >= qty_needed:
                batch.qty_remaining = Decimal(str(batch.qty_remaining or 0)) - Decimal(str(qty_needed))
                qty_needed = 0
            else:
                batch.qty_remaining = 0
                qty_needed -= available

        db.session.commit()
        return waste

    except Exception:
        db.session.rollback()
        raise


def create_count_session(branch_id: int, session_name: str,
                         started_by: int) -> InventoryCountSession:
    """Creates a new inventory count session with all branch ingredients."""
    try:
        session = InventoryCountSession(
            branch_id=branch_id,
            session_name=session_name,
            started_by=started_by,
            status='open'
        )
        db.session.add(session)
        db.session.flush()

        ingredients = Ingredient.query.filter_by(branch_id=branch_id).all()
        for ing in ingredients:
            item = InventoryCountItem(
                session_id=session.session_id,
                ingredient_id=ing.ingredient_id,
                system_qty=ing.qty_in_stock
            )
            db.session.add(item)

        db.session.commit()
        return session
    except Exception:
        db.session.rollback()
        raise


def submit_count(session_id: int, counts: list) -> InventoryCountSession:
    """Submits physical counts. Blocks double-submit via status check."""
    session = db.session.get(InventoryCountSession, session_id)
    if not session or session.status != 'open':
        raise ValueError("Session not open or already submitted")

    try:
        for count_data in counts:
            item = InventoryCountItem.query.filter_by(
                session_id=session_id,
                ingredient_id=count_data['ingredient_id']
            ).first()
            if item:
                item.counted_qty = count_data['counted_qty']
                item.variance_qty = float(item.counted_qty) - float(item.system_qty)

        session.status = 'completed'
        from datetime import datetime
        session.completed_at = datetime.utcnow()
        db.session.commit()
        return session
    except Exception:
        db.session.rollback()
        raise


def confirm_count_adjustment(session_id: int, confirmed_by: int) -> None:
    """Applies variance adjustments from a completed count session."""
    session = db.session.get(InventoryCountSession, session_id)
    if not session or session.status != 'completed':
        raise ValueError("Session not completed")

    try:
        items = InventoryCountItem.query.filter_by(session_id=session_id).all()
        for item in items:
            if item.variance_qty and item.variance_qty != 0:
                adjust_stock(
                    item.ingredient_id, float(item.counted_qty),
                    confirmed_by, f"Inventory Count Session {session_id}"
                )
    except Exception:
        db.session.rollback()
        raise


def get_low_stock_items(branch_id: int) -> list:
    """Returns ingredients below reorder level for a branch."""
    return Ingredient.query.filter(
        Ingredient.branch_id == branch_id,
        Ingredient.qty_in_stock < Ingredient.reorder_level
    ).all()


def create_supplier(name: str, contact_name: str = None, phone: str = None,
                    email: str = None, address: str = None, image_path: str = None,
                    notes: str = None, is_preferred: int = 0, changed_by: int = None) -> Supplier:
    """Registers a supplier."""
    try:
        supplier = Supplier(
            name=name,
            contact_name=contact_name,
            phone=phone,
            email=email,
            address=address,
            image_path=image_path,
            notes=notes,
            is_preferred=is_preferred,
            is_active=1
        )
        db.session.add(supplier)
        db.session.flush()

        if changed_by:
            from app.models import AuditLog
            audit = AuditLog(
                table_name='suppliers',
                record_id=supplier.supplier_id,
                action='INSERT',
                changed_by=changed_by,
                old_values='',
                new_values=f"name={name}, contact={contact_name}"
            )
            db.session.add(audit)

        db.session.commit()
        return supplier
    except Exception:
        db.session.rollback()
        raise


def update_supplier(supplier_id: int, **kwargs) -> Supplier:
    """Updates an existing supplier's details."""
    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        raise ValueError(f'Supplier #{supplier_id} not found')
    
    changed_by = kwargs.pop('changed_by', None)
    allowed = ['name', 'contact_name', 'phone', 'email', 'address',
               'image_path', 'notes', 'is_preferred', 'is_active']
    try:
        old_val_list = []
        new_val_list = []
        for key in allowed:
            if key in kwargs and kwargs[key] is not None:
                old_val = getattr(supplier, key)
                new_val = kwargs[key]
                if old_val != new_val:
                    old_val_list.append(f"{key}={old_val}")
                    new_val_list.append(f"{key}={new_val}")
                    setattr(supplier, key, new_val)

        if (old_val_list or new_val_list) and changed_by:
            from app.models import AuditLog
            audit = AuditLog(
                table_name='suppliers',
                record_id=supplier_id,
                action='UPDATE',
                changed_by=changed_by,
                old_values=", ".join(old_val_list),
                new_values=", ".join(new_val_list)
            )
            db.session.add(audit)

        db.session.commit()
        return supplier
    except Exception:
        db.session.rollback()
        raise


def deactivate_supplier(supplier_id: int, changed_by: int = None) -> Supplier:
    """Toggles a supplier to inactive."""
    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        raise ValueError(f'Supplier #{supplier_id} not found')
    try:
        old_active = supplier.is_active
        new_active = 0 if old_active == 1 else 1
        supplier.is_active = new_active

        if changed_by:
            from app.models import AuditLog
            audit = AuditLog(
                table_name='suppliers',
                record_id=supplier_id,
                action='UPDATE',
                changed_by=changed_by,
                old_values=f"is_active={old_active}",
                new_values=f"is_active={new_active}"
            )
            db.session.add(audit)

        db.session.commit()
        return supplier
    except Exception:
        db.session.rollback()
        raise


def get_supplier_detail(supplier_id: int, branch_id: int) -> dict:
    """Returns full supplier profile with PO history, open orders, and ingredients supplied."""
    from datetime import datetime
    supplier = Supplier.query.get(supplier_id)
    if not supplier:
        raise ValueError(f'Supplier #{supplier_id} not found')
    
    # Recent POs (last 10)
    recent_pos = (PurchaseOrder.query
        .filter_by(branch_id=branch_id, supplier_id=supplier_id)
        .order_by(PurchaseOrder.created_at.desc())
        .limit(10).all())
    
    # Open POs
    open_pos = (PurchaseOrder.query
        .filter_by(branch_id=branch_id, supplier_id=supplier_id)
        .filter(PurchaseOrder.status.in_(['draft', 'approved', 'ordered', 'partially_received']))
        .order_by(PurchaseOrder.created_at.desc()).all())
    
    # Total spend
    total_spend = 0
    all_received = (PurchaseOrder.query
        .filter_by(branch_id=branch_id, supplier_id=supplier_id)
        .filter(PurchaseOrder.status.in_(['received', 'partially_received'])).all())
    for po in all_received:
        for item in po.items:
            total_spend += int((item.received_qty or 0) * item.unit_cost_cents)
    
    # Ingredients supplied (unique from PO items)
    ingredient_ids = set()
    for po in recent_pos:
        for item in po.items:
            ingredient_ids.add(item.ingredient_id)
    ingredients_supplied = (Ingredient.query
        .filter(Ingredient.ingredient_id.in_(ingredient_ids)).all() if ingredient_ids else [])
    
    return {
        'supplier_id': supplier.supplier_id,
        'name': supplier.name,
        'contact_name': supplier.contact_name or '',
        'phone': supplier.phone or '',
        'email': supplier.email or '',
        'address': supplier.address or '',
        'image_path': supplier.image_path or '',
        'notes': supplier.notes or '',
        'is_preferred': supplier.is_preferred,
        'is_active': supplier.is_active,
        'created_at': supplier.created_at.strftime('%Y-%m-%d') if supplier.created_at else 'N/A',
        'total_spend_cents': total_spend,
        'recent_pos': [{
            'po_number': po.po_number,
            'status': po.status,
            'created_at': po.created_at.strftime('%Y-%m-%d') if po.created_at else '',
            'expected_at': po.expected_at.strftime('%Y-%m-%d') if po.expected_at else '',
            'total_cents': sum(int((it.received_qty or it.ordered_qty or 0) * it.unit_cost_cents) for it in po.items)
        } for po in recent_pos],
        'open_pos_count': len(open_pos),
        'ingredients_supplied': [{'id': i.ingredient_id, 'name': i.name, 'unit': i.unit} for i in ingredients_supplied]
    }


def create_purchase_order(branch_id: int, supplier_id: int, items: list,
                          expected_at=None, notes: str = None, created_by: int = 1) -> PurchaseOrder:
    """Creates a new purchase order with items and audit trail."""
    from app.models import AuditLog
    from datetime import datetime
    from decimal import Decimal

    try:
        # Generate PO number
        count = PurchaseOrder.query.filter_by(branch_id=branch_id).count()
        po_number = f"PO-{branch_id}-{datetime.utcnow().strftime('%Y%m%d')}-{count + 1:04d}"

        po = PurchaseOrder(
            branch_id=branch_id,
            supplier_id=supplier_id,
            po_number=po_number,
            status='draft',
            expected_at=expected_at,
            notes=notes,
            created_by=created_by
        )
        db.session.add(po)
        db.session.flush()

        for item in items:
            ordered_qty = Decimal(str(item['ordered_qty']))
            unit_cost_cents = int(item['unit_cost_cents'])
            line_total_cents = int(float(ordered_qty) * unit_cost_cents)

            po_item = PurchaseOrderItem(
                purchase_order_id=po.purchase_order_id,
                ingredient_id=item['ingredient_id'],
                ordered_qty=ordered_qty,
                received_qty=0.0,
                unit_cost_cents=unit_cost_cents,
                line_total_cents=line_total_cents,
                notes=item.get('notes')
            )
            db.session.add(po_item)

        audit = AuditLog(
            table_name='purchase_orders',
            record_id=po.purchase_order_id,
            action='INSERT',
            changed_by=created_by,
            new_values=f"po_number={po_number}, status=draft"
        )
        db.session.add(audit)
        db.session.commit()
        return po
    except Exception:
        db.session.rollback()
        raise


def approve_purchase_order(po_id: int, approved_by: int) -> PurchaseOrder:
    """Approves a purchase order, moving it to ordered status."""
    from app.models import AuditLog
    from datetime import datetime
    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        raise ValueError("Purchase order not found")
    if po.status != 'draft':
        raise ValueError("Only draft orders can be approved")

    try:
        old_status = po.status
        po.status = 'ordered'
        po.ordered_at = datetime.utcnow()
        po.approved_by = approved_by
        po.approved_at = datetime.utcnow()

        audit = AuditLog(
            table_name='purchase_orders',
            record_id=po_id,
            action='UPDATE',
            changed_by=approved_by,
            old_values=f"status={old_status}",
            new_values="status=ordered"
        )
        db.session.add(audit)
        db.session.commit()
        return po
    except Exception:
        db.session.rollback()
        raise


def receive_purchase_order(po_id: int, received_items: list,
                          invoice_ref: str, received_by: int) -> PurchaseOrder:
    """Processes receiving of purchase order items, increments stock, creates batches."""
    from app.models import AuditLog, StockBatch, SupplierPriceHistory
    from decimal import Decimal
    from datetime import datetime

    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        raise ValueError("Purchase order not found")
    if po.status not in ('approved', 'ordered', 'partially_received'):
        raise ValueError(f"Purchase order cannot be received in status: {po.status}")

    try:
        old_status = po.status
        po.received_at = datetime.utcnow()
        po.received_by = received_by
        po.invoice_ref = invoice_ref

        for item_data in received_items:
            poi_id = int(item_data['purchase_order_item_id'])
            received_qty = Decimal(str(item_data['received_qty']))
            actual_unit_cost_cents = int(item_data['actual_unit_cost_cents'])
            expiry_date = item_data.get('expiry_date')
            supplier_ref = item_data.get('supplier_ref') or invoice_ref
            item_notes = item_data.get('notes')

            poi = db.session.get(PurchaseOrderItem, poi_id)
            if not poi or poi.purchase_order_id != po_id:
                raise ValueError("Item does not belong to this purchase order")

            # Update received qty & cost
            poi.received_qty = Decimal(str(poi.received_qty or 0)) + received_qty
            poi.unit_cost_cents = actual_unit_cost_cents
            poi.line_total_cents = int(float(poi.received_qty) * actual_unit_cost_cents)

            if received_qty > 0:
                # 1. Create Stock Batch
                batch = StockBatch(
                    ingredient_id=poi.ingredient_id,
                    qty_received=received_qty,
                    qty_remaining=received_qty,
                    cost_per_unit_cents=actual_unit_cost_cents,
                    expiry_date=expiry_date,
                    supplier_ref=supplier_ref,
                    notes=item_notes
                )
                db.session.add(batch)

                # 2. Update Ingredient
                ingredient = db.session.get(Ingredient, poi.ingredient_id)
                if ingredient:
                    ingredient.qty_in_stock = Decimal(str(ingredient.qty_in_stock or 0)) + received_qty
                    ingredient.cost_per_unit_cents = actual_unit_cost_cents

                # 3. Supplier Price History
                history = SupplierPriceHistory(
                    supplier_id=po.supplier_id,
                    ingredient_id=poi.ingredient_id,
                    unit_cost_cents=actual_unit_cost_cents,
                    recorded_at=datetime.utcnow()
                )
                db.session.add(history)

        # Re-evaluate PO status
        all_received = True
        any_received = False
        for item in po.items:
            if item.received_qty < item.ordered_qty:
                all_received = False
            if item.received_qty > 0:
                any_received = True

        if all_received:
            po.status = 'received'
        elif any_received:
            po.status = 'partially_received'

        audit = AuditLog(
            table_name='purchase_orders',
            record_id=po_id,
            action='UPDATE',
            changed_by=received_by,
            old_values=f"status={old_status}",
            new_values=f"status={po.status}"
        )
        db.session.add(audit)
        db.session.commit()
        return po
    except Exception:
        db.session.rollback()
        raise


def cancel_purchase_order(po_id: int, reason: str, cancelled_by: int) -> PurchaseOrder:
    """Cancels a purchase order."""
    from app.models import AuditLog
    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        raise ValueError("Purchase order not found")
    if po.status in ('received', 'cancelled'):
        raise ValueError(f"Cannot cancel purchase order in status: {po.status}")

    try:
        old_status = po.status
        po.status = 'cancelled'

        audit = AuditLog(
            table_name='purchase_orders',
            record_id=po_id,
            action='UPDATE',
            changed_by=cancelled_by,
            old_values=f"status={old_status}, notes={po.notes}",
            new_values=f"status=cancelled, cancel_reason={reason}"
        )
        db.session.add(audit)
        db.session.commit()
        return po
    except Exception:
        db.session.rollback()
        raise


def get_open_purchase_orders(branch_id: int) -> list:
    """Returns open purchase orders for a branch."""
    return PurchaseOrder.query.filter(
        PurchaseOrder.branch_id == branch_id,
        PurchaseOrder.status.in_(['draft', 'approved', 'ordered', 'partially_received'])
    ).order_by(PurchaseOrder.created_at.desc()).all()


def get_purchase_order_summary(po_id: int) -> PurchaseOrder:
    """Returns details of a purchase order."""
    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        raise ValueError("Purchase order not found")
    return po


def get_spend_by_supplier(branch_id: int) -> list:
    """Aggregates received line totals by supplier."""
    from sqlalchemy import func
    results = (db.session.query(
        Supplier.supplier_id,
        Supplier.name,
        Supplier.image_path,
        func.sum(PurchaseOrderItem.received_qty * PurchaseOrderItem.unit_cost_cents).label('spend')
    ).join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.supplier_id)
     .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.purchase_order_id)
     .filter(PurchaseOrder.branch_id == branch_id)
     .filter(PurchaseOrder.status.in_(['received', 'partially_received']))
     .group_by(Supplier.supplier_id, Supplier.name, Supplier.image_path)
     .all())

    return [{'supplier_id': r[0], 'name': r[1], 'image_path': r[2], 'total_spend_cents': int(r[3] or 0)} for r in results]


def get_price_change_history(branch_id: int) -> list:
    """Returns historical supplier price records for branch ingredients."""
    return (SupplierPriceHistory.query
            .join(Ingredient, Ingredient.ingredient_id == SupplierPriceHistory.ingredient_id)
            .filter(Ingredient.branch_id == branch_id)
            .order_by(SupplierPriceHistory.recorded_at.desc())
            .limit(50)
            .all())


def get_overdue_purchase_orders(branch_id: int) -> list:
    """Returns purchase orders past their expected delivery date."""
    from datetime import datetime
    return (PurchaseOrder.query
            .filter(PurchaseOrder.branch_id == branch_id)
            .filter(PurchaseOrder.status.in_(['ordered', 'partially_received']))
            .filter(PurchaseOrder.expected_at < datetime.utcnow())
            .order_by(PurchaseOrder.expected_at.asc())
            .all())


def get_supplier_performance_insights(branch_id: int) -> dict:
    """Calculates performance insights for each supplier in a branch."""
    from datetime import datetime
    from app.models import Supplier
    suppliers = Supplier.query.all()  # Show all suppliers (active + inactive) in directory
    insights = {}
    
    for s in suppliers:
        # Fetch received POs for this supplier
        received_pos = PurchaseOrder.query.filter_by(
            branch_id=branch_id,
            supplier_id=s.supplier_id,
            status='received'
        ).all()
        
        # Calculate spend
        total_spend_cents = 0
        on_time_count = 0
        lead_time_days_sum = 0
        
        for po in received_pos:
            # Calculate spend
            for item in po.items:
                total_spend_cents += int((item.received_qty or 0) * item.unit_cost_cents)
            
            # On-time delivery check
            if po.expected_at and po.received_at:
                if po.received_at.date() <= po.expected_at.date():
                    on_time_count += 1
            
            # Lead time calculation (days between ordered and received)
            if po.ordered_at and po.received_at:
                diff = po.received_at - po.ordered_at
                lead_time_days_sum += max(0, diff.days)
                
        total_received = len(received_pos)
        on_time_pct = (on_time_count / total_received * 100) if total_received > 0 else 100.0
        avg_lead_time = (lead_time_days_sum / total_received) if total_received > 0 else 0.0
        
        # Overdue deliveries count
        overdue_count = PurchaseOrder.query.filter_by(
            branch_id=branch_id,
            supplier_id=s.supplier_id
        ).filter(PurchaseOrder.status.in_(['ordered', 'partially_received']))\
         .filter(PurchaseOrder.expected_at < datetime.utcnow()).count()
         
        # Last order date
        last_po = PurchaseOrder.query.filter_by(
            branch_id=branch_id,
            supplier_id=s.supplier_id
        ).filter(PurchaseOrder.status != 'draft')\
         .order_by(PurchaseOrder.created_at.desc()).first()
         
        insights[s.supplier_id] = {
            'supplier_id': s.supplier_id,
            'name': s.name,
            'image_path': s.image_path,
            'total_spend_cents': total_spend_cents,
            'on_time_pct': round(on_time_pct, 1),
            'overdue_count': overdue_count,
            'avg_lead_time': round(avg_lead_time, 1),
            'last_order_date': last_po.created_at.strftime('%Y-%m-%d') if last_po else 'N/A'
        }
    return insights


def create_ingredient(name: str, unit: str, reorder_level: float,
                      default_supplier_id: int = None, current_qty: float = 0.0,
                      branch_id: int = None, image_path: str = None) -> Ingredient:
    """Creates a new ingredient, optionally setting up initial stock batch."""
    from app.models import StockBatch, AuditLog
    from decimal import Decimal
    
    try:
        qty = Decimal(str(current_qty or 0.0))
        ing = Ingredient(
            name=name,
            unit=unit,
            qty_in_stock=qty,
            reorder_level=Decimal(str(reorder_level)),
            default_supplier_id=default_supplier_id if default_supplier_id and default_supplier_id > 0 else None,
            branch_id=branch_id,
            is_active=1,
            image_path=image_path
        )
        db.session.add(ing)
        db.session.flush()
        
        # If initial stock is specified, create an initial batch
        if qty > 0:
            batch = StockBatch(
                ingredient_id=ing.ingredient_id,
                qty_received=qty,
                qty_remaining=qty,
                cost_per_unit_cents=0,
                notes="Initial stock setup"
            )
            db.session.add(batch)
            
        audit = AuditLog(
            table_name='ingredients',
            record_id=ing.ingredient_id,
            action='INSERT',
            new_values=f"name={name}, unit={unit}, qty_in_stock={qty}"
        )
        db.session.add(audit)
        db.session.commit()
        return ing
    except Exception:
        db.session.rollback()
        raise


def update_ingredient(ingredient_id: int, name: str, unit: str,
                      reorder_level: float, default_supplier_id: int = None,
                      is_active: int = 1, image_path: str = None) -> Ingredient:
    """Updates an existing ingredient's details and active status."""
    from app.models import AuditLog
    from decimal import Decimal
    
    ing = db.session.get(Ingredient, ingredient_id)
    if not ing:
        raise ValueError("Ingredient not found")
        
    try:
        old_values = f"name={ing.name}, unit={ing.unit}, reorder_level={ing.reorder_level}, is_active={ing.is_active}, image_path={ing.image_path}"
        
        ing.name = name
        ing.unit = unit
        ing.reorder_level = Decimal(str(reorder_level))
        ing.default_supplier_id = default_supplier_id if default_supplier_id and default_supplier_id > 0 else None
        ing.is_active = is_active
        if image_path is not None:
            ing.image_path = image_path
        
        new_values = f"name={name}, unit={unit}, reorder_level={reorder_level}, is_active={is_active}, image_path={ing.image_path}"
        
        audit = AuditLog(
            table_name='ingredients',
            record_id=ingredient_id,
            action='UPDATE',
            old_values=old_values,
            new_values=new_values
        )
        db.session.add(audit)
        db.session.commit()
        return ing
    except Exception:
        db.session.rollback()
        raise


def get_ingredient_history(ingredient_id: int) -> list:
    """Returns chronological change history for an ingredient."""
    from app.models import AuditLog, WasteLog, StockBatch, Employee
    history = []
    
    # 1. Fetch WasteLogs (Removals)
    waste_logs = WasteLog.query.filter_by(ingredient_id=ingredient_id).all()
    for w in waste_logs:
        history.append({
            'date': w.created_at.strftime('%Y-%m-%d %H:%M'),
            'timestamp': w.created_at,
            'action': 'Stock Removed',
            'qty_change': f"-{w.qty}",
            'reason': w.reason or 'Waste/Damage',
            'user': w.recorder.full_name if w.recorder else 'N/A'
        })
        
    # 2. Fetch StockBatches (Additions)
    batches = StockBatch.query.filter_by(ingredient_id=ingredient_id).all()
    for b in batches:
        reason = b.notes or 'Stock added informally'
        action = 'Stock Added'
        if b.supplier_ref:
            reason += f" (Ref: {b.supplier_ref})"
        
        history.append({
            'date': b.received_at.strftime('%Y-%m-%d %H:%M'),
            'timestamp': b.received_at,
            'action': action,
            'qty_change': f"+{b.qty_received}",
            'reason': reason,
            'user': 'N/A'
        })
        
    # 3. Fetch AuditLogs (Manual Stock Updates and Counts)
    audit_logs = AuditLog.query.filter_by(table_name='ingredients', record_id=ingredient_id).all()
    for a in audit_logs:
        old_qty = None
        new_qty = None
        reason = 'Manual update'
        
        try:
            if a.old_values and 'qty_in_stock=' in a.old_values:
                old_qty = float(a.old_values.split('qty_in_stock=')[1].split(',')[0])
            if a.new_values and 'qty_in_stock=' in a.new_values:
                new_qty = float(a.new_values.split('qty_in_stock=')[1].split(',')[0])
            if a.new_values and 'reason=' in a.new_values:
                reason = a.new_values.split('reason=')[1]
        except Exception:
            pass
            
        qty_change = '0.0'
        if old_qty is not None and new_qty is not None:
            diff = new_qty - old_qty
            qty_change = f"+{diff}" if diff > 0 else f"{diff}"
            
        user_name = 'System/Unknown'
        if a.changed_by:
            emp = Employee.query.get(a.changed_by)
            if emp:
                user_name = emp.full_name
                
        if old_qty == new_qty:
            continue
            
        history.append({
            'date': a.changed_at.strftime('%Y-%m-%d %H:%M'),
            'timestamp': a.changed_at,
            'action': 'Stock Count Confirmed' if 'Count' in reason else 'Stock Updated',
            'qty_change': qty_change,
            'reason': reason,
            'user': user_name
        })
        
    history.sort(key=lambda x: x['timestamp'], reverse=True)
    return history
