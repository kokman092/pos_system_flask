from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.decorators import role_required
from app.services import kds_service
from app.utils.response import success_response, error_response

kitchen_bp = Blueprint('kitchen', __name__, url_prefix='/kitchen')


@kitchen_bp.before_request
@login_required
@role_required('admin', 'manager', 'cashier', 'waiter', 'kitchen')
def limit_kitchen_access():
    pass

@kitchen_bp.route('', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'kitchen', 'cashier')
def index():
    """Kitchen screen — passes active kitchen orders grouped by order."""
    from app.models import Order, OrderItem
    from sqlalchemy.orm import joinedload
    kitchen_orders = Order.query.filter(
        Order.branch_id == current_user.branch_id,
        Order.status.in_(['open', 'confirmed', 'served'])
    ).options(
        joinedload(Order.items).joinedload(OrderItem.menu_item),
        joinedload(Order.table)
    ).all()
    # Filter to only orders that have items in 'kitchen' status
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
    return render_template('app/kitchen.html', orders=orders)

@kitchen_bp.route('/api/tickets', methods=['GET'])
@login_required
def get_tickets():
    try:
        tickets = kds_service.get_active_tickets(current_user.branch_id)
        return success_response([{"item_id": t['item'].order_item_id} for t in tickets])
    except Exception as e:
        return error_response(str(e))

@kitchen_bp.route('/api/serve/<int:item_id>', methods=['POST'])
@login_required
def serve(item_id):
    try:
        kds_service.mark_ticket_served(item_id)
        return success_response()
    except Exception as e:
        return error_response(str(e))

@kitchen_bp.route('/api/warnings', methods=['GET'])
@login_required
def warnings():
    try:
        warns = kds_service.get_timing_warnings(current_user.branch_id)
        return success_response([{"item_id": w['item'].order_item_id} for w in warns])
    except Exception as e:
        return error_response(str(e))
