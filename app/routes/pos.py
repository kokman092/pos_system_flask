from flask import Blueprint, render_template, request, make_response
from flask_login import login_required, current_user
from app.forms.order_forms import CreateOrderForm, AddItemForm, PaymentForm, ApplyDiscountForm, CancelItemForm
from app.services import order_service
from app.utils.response import success_response, error_response
from app.utils.money import display_to_cents
from app.models import RestaurantTable, MenuItem

from app.decorators import role_required, permission_required

pos_bp = Blueprint('pos', __name__, url_prefix='/pos')


@pos_bp.before_request
@login_required
@permission_required('pos', 'view')
def limit_pos_access():
    if request.is_json and request.json:
        for key in list(request.json.keys()):
            if request.json[key] is None:
                request.json.pop(key)

@pos_bp.route('', methods=['GET'])
@login_required
@permission_required('pos', 'view')
def pos_index():
    """POS screen — passes tables, categories, items for the order interface."""
    tables = RestaurantTable.query.filter_by(
        branch_id=current_user.branch_id,
        is_active=1
    ).order_by(RestaurantTable.table_number).all()
    from app.models import Category
    categories = Category.query.filter_by(is_active=1).order_by(Category.display_order).all()
    items = MenuItem.query.filter_by(is_active=1, is_available=1).filter(
        (MenuItem.branch_id == current_user.branch_id) | (MenuItem.branch_id.is_(None))
    ).all()
    
    response = make_response(render_template('app/pos.html',
                           tables=tables,
                           categories=categories,
                           items=items))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@pos_bp.route('/api/orders', methods=['POST'])
@login_required
@permission_required('pos', 'create_sale')
def create_order():
    form = CreateOrderForm(data=request.json)
    if form.validate():
        try:
            order = order_service.create_order(current_user.branch_id, form.table_id.data, current_user.employee_id, form.order_type.data, form.pax.data, form.notes.data)
            return success_response({"order_id": order.order_id})
        except Exception as e:
            return error_response(str(e))
    return error_response("Validation failed", 422, form.errors)

@pos_bp.route('/api/orders/<int:id>', methods=['GET'])
@login_required
@permission_required('pos', 'view')
def get_order(id):
    try:
        data = order_service.get_order_summary(id)
        return success_response({"order_id": id, "total": data['total_cents']})
    except Exception as e:
        return error_response(str(e))

@pos_bp.route('/api/orders/<int:id>/items', methods=['POST'])
@login_required
@permission_required('pos', 'create_sale')
def add_item(id):
    form = AddItemForm(data=request.json)
    if form.validate():
        try:
            item = order_service.add_item(id, form.item_id.data, form.quantity.data, form.notes.data, form.seat_number.data, form.modifier_ids.data)
            return success_response({"order_item_id": item.order_item_id})
        except Exception as e:
            return error_response(str(e))
    return error_response("Validation failed", 422, form.errors)

@pos_bp.route('/api/orders/<int:id>/send-kitchen', methods=['POST'])
@login_required
@permission_required('pos', 'create_sale')
def send_kitchen(id):
    item_ids = request.json.get('order_item_ids', [])
    try:
        items = order_service.send_to_kitchen(id, item_ids)
        return success_response({"sent": len(items)})
    except Exception as e:
        return error_response(str(e))

@pos_bp.route('/api/orders/<int:id>/pay', methods=['POST'])
@login_required
@permission_required('pos', 'create_sale')
def pay(id):
    form = PaymentForm(data=request.json)
    if form.validate():
        try:
            amount = display_to_cents(form.amount.data)
            tendered = display_to_cents(form.tendered.data) if form.tendered.data else amount
            pay = order_service.process_payment(id, form.method.data, amount, tendered, form.reference_no.data, current_user.employee_id)
            return success_response({"payment_id": pay.payment_id})
        except Exception as e:
            return error_response(str(e))
    return error_response("Validation failed", 422, form.errors)

@pos_bp.route('/api/orders/<int:id>/cancel', methods=['POST'])
@login_required
@permission_required('pos', 'void_bill')
def cancel(id):
    try:
        order_service.cancel_order(id, request.json.get('reason'), current_user.employee_id)
        return success_response()
    except Exception as e:
        return error_response(str(e))

@pos_bp.route('/api/orders/<int:id>/discount', methods=['POST'])
@login_required
@permission_required('pos', 'apply_discount')
def discount(id):
    return success_response()

@pos_bp.route('/api/orders/<int:id>/items/<int:item_id>', methods=['DELETE'])
@login_required
@permission_required('pos', 'void_bill')
def delete_item(id, item_id):
    form = CancelItemForm(data=request.json)
    if form.validate():
        try:
            order_service.cancel_item(form.order_item_id.data, form.reason.data, current_user.employee_id)
            return success_response()
        except Exception as e:
            return error_response(str(e))
    return error_response("Validation failed", 422, form.errors)

@pos_bp.route('/api/tables', methods=['GET'])
@login_required
@permission_required('pos', 'view')
def tables():
    tables = RestaurantTable.query.filter_by(branch_id=current_user.branch_id).all()
    return success_response([{"id": t.table_id, "status": t.status} for t in tables])


@pos_bp.route('/api/tables/<int:table_id>/active-order', methods=['GET'])
@login_required
@permission_required('pos', 'view')
def active_order(table_id):
    """Retrieves the open order for a given table."""
    from app.models import Order
    order = Order.query.filter_by(table_id=table_id, status='open').first()
    if not order:
        return success_response(None)
    
    items_data = []
    for item in order.items:
        if item.status != 'cancelled':
            items_data.append({
                'order_item_id': item.order_item_id,
                'item_id': item.item_id,
                'name': item.menu_item.name if item.menu_item else 'Unknown',
                'quantity': item.quantity,
                'unit_price_cents': item.unit_price_cents,
                'status': item.status,
                'notes': item.notes
            })
        
    return success_response({
        'order_id': order.order_id,
        'table_id': order.table_id,
        'order_type': order.order_type,
        'pax': order.pax,
        'status': order.status,
        'items': items_data
    })


@pos_bp.route('/api/menu', methods=['GET'])
@login_required
@permission_required('pos', 'view')
def menu():
    """Returns menu items for the current user's branch."""
    items = MenuItem.query.filter_by(is_active=1, is_available=1).filter(
        (MenuItem.branch_id == current_user.branch_id) | (MenuItem.branch_id.is_(None))
    ).all()
    return success_response([{"id": i.item_id, "name": i.name, "price_cents": i.price_cents} for i in items])

