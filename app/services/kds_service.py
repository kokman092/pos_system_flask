"""KDS Service — handles kitchen display system ticket routing and status.

get_active_tickets uses a single joined query instead of N+1 per-row lookups.
"""
from datetime import datetime
from extensions import db
from app.models import OrderItem, KdsStation, KdsLog, MenuItem, Order, RestaurantTable


from sqlalchemy.orm import joinedload


def route_to_station(order_item: OrderItem) -> KdsLog:
    """Routes an order item to the appropriate KDS station."""
    menu_item = db.session.get(MenuItem, order_item.item_id)
    if not menu_item:
        raise ValueError("Menu item not found")

    order = db.session.get(Order, order_item.order_id)
    station = KdsStation.query.filter_by(
        branch_id=order.branch_id, is_active=1
    ).first()

    try:
        log = KdsLog(
            order_item_id=order_item.order_item_id,
            station_id=station.station_id if station else None,
            displayed_at=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()
        return log
    except Exception:
        db.session.rollback()
        raise


def get_active_tickets(branch_id: int, station_id: int = None) -> list:
    """Returns active kitchen tickets using a single joined query.
    Loads everything needed in one query with joinedload.
    No lazy-loading allowed on this function.
    """
    query = db.session.query(OrderItem)\
        .options(
            joinedload(OrderItem.order).joinedload(Order.table),
            joinedload(OrderItem.menu_item)
        )\
        .join(Order)\
        .filter(
            Order.branch_id == branch_id,
            OrderItem.status == 'kitchen'
        )

    if station_id:
        query = query.join(KdsLog, OrderItem.order_item_id == KdsLog.order_item_id)\
            .filter(KdsLog.station_id == station_id)

    results = query.order_by(OrderItem.sent_at.asc()).limit(100).all()
    tickets = []
    for item in results:
        elapsed = 0
        if item.sent_at:
            elapsed = int((datetime.utcnow() - item.sent_at).total_seconds() / 60)

        tickets.append({
            'order': item.order,
            'table': item.order.table if item.order else None,
            'item': item,
            'seat_number': item.seat_number,
            'modifiers': [],
            'elapsed_minutes': elapsed
        })
    return tickets


def mark_ticket_served(order_item_id: int) -> OrderItem:
    """Marks a kitchen ticket as served via order_service state machine."""
    from app.services.order_service import update_item_status
    return update_item_status(order_item_id, 'served')


def get_timing_warnings(branch_id: int) -> list:
    """Returns tickets that have been in the kitchen for over 15 minutes."""
    tickets = get_active_tickets(branch_id)
    return [t for t in tickets if t['elapsed_minutes'] > 15]


def get_ticket_summary(branch_id: int) -> list:
    """Returns lightweight list of active order_item_ids for KDS diff check.
    Used by the DOM-patch JS to detect new/removed tickets without full reload.
    """
    results = db.session.query(OrderItem.order_item_id)\
        .join(Order)\
        .filter(
            Order.branch_id == branch_id,
            OrderItem.status == 'kitchen'
        ).all()
    return [r.order_item_id for r in results]
