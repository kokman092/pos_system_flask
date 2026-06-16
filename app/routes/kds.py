from flask import Blueprint, render_template, Response, jsonify
from flask_login import login_required, current_user
from app.services import kds_service
import time

from app.decorators import role_required

kds_bp = Blueprint('kds', __name__, url_prefix='/kds')


@kds_bp.before_request
@login_required
@role_required('admin', 'manager', 'kitchen')
def limit_kds_access():
    pass


@kds_bp.route('', methods=['GET'])
@login_required
def index():
    """KDS main screen — passes active kitchen orders grouped by order."""
    from app.models import Order, OrderItem
    from sqlalchemy.orm import joinedload
    kitchen_orders = Order.query.filter(
        Order.branch_id == current_user.branch_id,
        Order.status.in_(['open', 'confirmed', 'served'])
    ).options(
        joinedload(Order.items).joinedload(OrderItem.menu_item),
        joinedload(Order.table)
    ).all()
    orders = []
    from datetime import datetime
    for o in kitchen_orders:
        kitchen_items = [i for i in o.items if i.status == 'kitchen']
        if kitchen_items:
            elapsed = int((datetime.utcnow() - o.opened_at).total_seconds() / 60) if o.opened_at else 0
            orders.append({
                'order': o,
                'table': o.table,
                'items': kitchen_items,
                'elapsed_min': elapsed
            })
    ticket_count = sum(len(o['items']) for o in orders)
    return render_template('app/kds.html', orders=orders, ticket_count=ticket_count)


@kds_bp.route('/<int:station_id>', methods=['GET'])
@login_required
def station(station_id):
    """KDS station-specific screen — passes filtered orders."""
    tickets = kds_service.get_active_tickets(current_user.branch_id, station_id)
    # Group tickets by order
    order_map = {}
    from datetime import datetime
    for t in tickets:
        oid = t['order'].order_id
        if oid not in order_map:
            o = t['order']
            elapsed = int((datetime.utcnow() - o.opened_at).total_seconds() / 60) if o.opened_at else 0
            order_map[oid] = {
                'order': o,
                'table': t['table'],
                'items': [],
                'elapsed_min': elapsed
            }
        order_map[oid]['items'].append(t['item'])
    orders = list(order_map.values())
    ticket_count = sum(len(o['items']) for o in orders)
    return render_template('app/kds.html', orders=orders, station_id=station_id, ticket_count=ticket_count)


@kds_bp.route('/api/tickets', methods=['GET'])
@login_required
def tickets_api():
    """JSON endpoint returning current active ticket IDs.
    Used by the KDS DOM-patch JS for lightweight diff checking.
    """
    ticket_ids = kds_service.get_ticket_summary(current_user.branch_id)
    return jsonify({'success': True, 'data': ticket_ids, 'count': len(ticket_ids)})


@kds_bp.route('/api/stream', methods=['GET'])
@login_required
def stream():
    """Server-Sent Events stream for real-time KDS heartbeat.
    Sends a heartbeat every 5 seconds, max 120 pulses (10 min) before closing.
    Client should reconnect automatically via EventSource API.
    """
    def event_stream():
        max_beats = 120  # 10 minutes, then client reconnects
        for _ in range(max_beats):
            time.sleep(5)
            yield "data: heartbeat\n\n"
    return Response(event_stream(), mimetype="text/event-stream")
