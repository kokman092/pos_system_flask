from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.decorators import role_required, permission_required
from app.forms.inventory_forms import AddStockBatchForm, AdjustStockForm, WasteLogForm, IngredientForm
from app.services import inventory_service
from app.models import Ingredient
from app.utils.response import success_response
from app.utils.money import display_to_cents

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')


@inventory_bp.before_request
@login_required
def limit_inventory_access():
    if not (current_user.has_permission('inventory', 'view') or
            current_user.has_permission('suppliers', 'view') or
            current_user.has_permission('purchasing', 'view')):
        return render_template('errors/403.html'), 403


@inventory_bp.route('', methods=['GET'])
@login_required
def index():
    """Inventory page — passes ingredients, suppliers, POs, and reports."""
    from app.models import InventoryCountSession, Supplier, PurchaseOrder, SupplierPriceHistory
    from app.forms.inventory_forms import SupplierForm, PurchaseOrderForm

    active_tab = request.args.get('active_tab', 'stock')

    ingredients = Ingredient.query.filter_by(
        branch_id=current_user.branch_id
    ).order_by(Ingredient.name).all()
    
    low_stock = [i for i in ingredients
                 if float(i.qty_in_stock or 0) <= float(i.reorder_level or 0)]

    active_session = InventoryCountSession.query.filter_by(
        branch_id=current_user.branch_id,
        status='open'
    ).first()

    completed_sessions = InventoryCountSession.query.filter_by(
        branch_id=current_user.branch_id,
        status='completed'
    ).all()

    # Fetch Suppliers and POs
    suppliers = Supplier.query.order_by(Supplier.name).all()
    purchase_orders = PurchaseOrder.query.filter_by(
        branch_id=current_user.branch_id
    ).order_by(PurchaseOrder.created_at.desc()).all()

    # Fetch Reports Data
    spend_by_supplier = inventory_service.get_spend_by_supplier(current_user.branch_id)
    price_history = inventory_service.get_price_change_history(current_user.branch_id)
    overdue_pos = inventory_service.get_overdue_purchase_orders(current_user.branch_id)
    supplier_insights = inventory_service.get_supplier_performance_insights(current_user.branch_id)

    # Map of ingredient ID to its last supplier ID
    last_suppliers = {}
    for ing in ingredients:
        last_price_rec = (SupplierPriceHistory.query
                          .filter_by(ingredient_id=ing.ingredient_id)
                          .order_by(SupplierPriceHistory.recorded_at.desc())
                          .first())
        if last_price_rec:
            last_suppliers[ing.ingredient_id] = last_price_rec.supplier_id

    # For supplier and ingredient choices in dynamic JS modals
    supplier_choices = [{'id': s.supplier_id, 'name': s.name} for s in suppliers]
    # Filter ingredient choices for PO creation to active ingredients only
    ingredient_choices = [{'id': i.ingredient_id, 'name': i.name, 'unit': i.unit, 'cost': float(i.cost_per_unit_cents / 100.0)} for i in ingredients if getattr(i, 'is_active', 1) == 1]

    ing_form = IngredientForm()
    ing_form.default_supplier_id.choices = [(0, 'Select Supplier (Optional)')] + [(s.supplier_id, s.name) for s in suppliers]

    return render_template('admin/inventory.html',
                           ingredients=ingredients,
                           low_stock=low_stock,
                           active_session=active_session,
                           completed_sessions=completed_sessions,
                           suppliers=suppliers,
                           purchase_orders=purchase_orders,
                           spend_by_supplier=spend_by_supplier,
                           price_history=price_history,
                           overdue_pos=overdue_pos,
                           supplier_insights=supplier_insights,
                           last_suppliers=last_suppliers,
                           active_tab=active_tab,
                           supplier_choices=supplier_choices,
                           ingredient_choices=ingredient_choices,
                           add_form=AddStockBatchForm(),
                           adjust_form=AdjustStockForm(),
                           waste_form=WasteLogForm(),
                           supplier_form=SupplierForm(),
                           po_form=PurchaseOrderForm(),
                           ingredient_form=ing_form)


@inventory_bp.route('/batch', methods=['POST'])
@login_required
@permission_required('inventory', 'edit')
def add_batch():
    form = AddStockBatchForm(request.form)
    reason = request.form.get('reason', 'Emergency/Informal Stock Added')
    note = request.form.get('note', '')
    combined_notes = f"Reason: {reason}"
    if note:
        combined_notes += f" | Note: {note}"
    if form.validate():
        try:
            inventory_service.add_stock_batch(
                form.ingredient_id.data, float(form.qty_received.data),
                display_to_cents(form.cost_per_unit.data),
                form.expiry_date.data, form.supplier_ref.data,
                current_user.branch_id, notes=combined_notes)
            flash('Stock added successfully', 'success')
        except Exception as e:
            flash(str(e), 'error')
    return redirect(url_for('inventory.index'))



@inventory_bp.route('/adjust', methods=['POST'])
@login_required
@permission_required('inventory', 'edit')
def adjust():
    form = AdjustStockForm(request.form)
    if form.validate():
        try:
            inventory_service.adjust_stock(
                form.ingredient_id.data, float(form.new_qty.data),
                current_user.employee_id, form.reason.data)
            flash('Stock updated successfully', 'success')
        except Exception as e:
            flash(str(e), 'error')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/waste', methods=['POST'])
@login_required
@permission_required('inventory', 'edit')
def waste():
    form = WasteLogForm(request.form)
    if form.validate():
        try:
            inventory_service.log_waste(
                form.ingredient_id.data, float(form.qty.data),
                form.reason.data, current_user.employee_id,
                current_user.branch_id)
            flash('Stock removed successfully', 'success')
        except Exception as e:
            flash(str(e), 'error')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/low-stock', methods=['GET'])
@login_required
def low_stock():
    items = inventory_service.get_low_stock_items(current_user.branch_id)
    return success_response([{
        'id': i.ingredient_id,
        'name': i.name,
        'qty': float(i.qty_in_stock or 0),
        'reorder': float(i.reorder_level or 0)
    } for i in items])


@inventory_bp.route('/count/start', methods=['POST'])
@login_required
def count_start():
    try:
        inventory_service.create_count_session(
            current_user.branch_id,
            request.form.get('session_name'),
            current_user.employee_id)
        flash('Stock count started', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/count/<int:id>/submit', methods=['POST'])
@login_required
def count_submit(id):
    try:
        ingredients = Ingredient.query.filter_by(branch_id=current_user.branch_id).all()
        counts = []
        for ing in ingredients:
            qty_val = request.form.get(f'counted_qty_{ing.ingredient_id}')
            if qty_val is not None and qty_val != '':
                counts.append({
                    'ingredient_id': ing.ingredient_id,
                    'counted_qty': float(qty_val)
                })
        
        if counts:
            inventory_service.submit_count(id, counts)
            flash('Counts submitted successfully', 'success')
        else:
            flash('No counts submitted', 'warning')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/count/<int:id>/confirm', methods=['POST'])
@login_required
@permission_required('inventory', 'edit')
def count_confirm(id):
    try:
        inventory_service.confirm_count_adjustment(id, current_user.employee_id)
        flash('Count confirmed and stock updated', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/suppliers', methods=['POST'])
@login_required
@permission_required('suppliers', 'create')
def add_supplier():
    from app.forms.inventory_forms import SupplierForm
    import os
    import time
    from werkzeug.utils import secure_filename
    from flask import current_app

    form = SupplierForm(request.form)
    if form.validate():
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                upload_dir = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
                image_path = f"img/uploads/{filename}"

        try:
            inventory_service.create_supplier(
                name=form.name.data,
                contact_name=form.contact_name.data,
                phone=form.phone.data,
                email=form.email.data,
                address=form.address.data,
                image_path=image_path or form.image_path.data,
                notes=form.notes.data,
                is_preferred=int(form.is_preferred.data or 0),
                changed_by=current_user.employee_id
            )
            flash('Supplier registered successfully', 'success')
        except Exception as e:
            flash(str(e), 'error')
    else:
        for field, errors in form.errors.items():
            flash(f"{field}: {', '.join(errors)}", 'error')
    return redirect(url_for('inventory.index', active_tab='suppliers'))


@inventory_bp.route('/suppliers/<int:id>/edit', methods=['POST'])
@login_required
@permission_required('suppliers', 'edit')
def edit_supplier(id):
    from app.forms.inventory_forms import SupplierForm
    import os
    import time
    from werkzeug.utils import secure_filename
    from flask import current_app

    form = SupplierForm(request.form)
    if form.validate():
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                upload_dir = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
                image_path = f"img/uploads/{filename}"

        try:
            update_data = {
                'name': form.name.data,
                'contact_name': form.contact_name.data,
                'phone': form.phone.data,
                'email': form.email.data,
                'address': form.address.data,
                'notes': form.notes.data,
                'is_preferred': int(form.is_preferred.data or 0),
                'is_active': int(form.is_active.data if form.is_active.data is not None else 1),
            }
            if image_path:
                update_data['image_path'] = image_path
            elif form.image_path.data:
                update_data['image_path'] = form.image_path.data

            inventory_service.update_supplier(id, changed_by=current_user.employee_id, **update_data)
            flash('Supplier updated successfully', 'success')
        except Exception as e:
            flash(str(e), 'error')
    else:
        for field, errors in form.errors.items():
            flash(f"{field}: {', '.join(errors)}", 'error')
    return redirect(url_for('inventory.index', active_tab='suppliers'))


@inventory_bp.route('/suppliers/<int:id>/deactivate', methods=['POST'])
@login_required
@permission_required('suppliers', 'delete')
def deactivate_supplier(id):
    try:
        supplier = inventory_service.deactivate_supplier(id, changed_by=current_user.employee_id)
        status = 'activated' if supplier.is_active == 1 else 'archived'
        flash(f'Supplier {status} successfully', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('inventory.index', active_tab='suppliers'))


@inventory_bp.route('/suppliers/<int:id>', methods=['GET'])
@login_required
@permission_required('suppliers', 'view')
def supplier_detail(id):
    from flask import jsonify
    try:
        detail = inventory_service.get_supplier_detail(id, current_user.branch_id)
        return jsonify(detail)
    except Exception as e:
        return {'error': str(e)}, 400


@inventory_bp.route('/purchase-orders', methods=['POST'])
@login_required
@permission_required('purchasing', 'create')
def add_purchase_order():
    from datetime import datetime
    
    # Check if request is JSON or form-data
    if request.is_json or request.headers.get('Content-Type') == 'application/json':
        data = request.json
        supplier_id = int(data.get('supplier_id'))
        expected_at_str = data.get('expected_at')
        expected_at = datetime.strptime(expected_at_str, '%Y-%m-%d') if expected_at_str else None
        notes = data.get('notes')
        
        items_data = []
        for item in data.get('items', []):
            items_data.append({
                'ingredient_id': int(item['ingredient_id']),
                'ordered_qty': float(item['ordered_qty']),
                'unit_cost_cents': int(float(item['unit_cost']) * 100)
            })
    else:
        supplier_id = int(request.form.get('supplier_id'))
        expected_at_str = request.form.get('expected_at')
        expected_at = datetime.strptime(expected_at_str, '%Y-%m-%d') if expected_at_str else None
        notes = request.form.get('notes')
        
        items_data = []
        item_indices = set()
        for key in request.form.keys():
            if key.startswith('items-') and '-' in key:
                parts = key.split('-')
                if len(parts) >= 2 and parts[1].isdigit():
                    item_indices.add(int(parts[1]))
                    
        for idx in sorted(item_indices):
            ing_id = request.form.get(f'items-{idx}-ingredient_id')
            qty = request.form.get(f'items-{idx}-ordered_qty')
            cost = request.form.get(f'items-{idx}-unit_cost')
            if ing_id and qty and cost:
                items_data.append({
                    'ingredient_id': int(ing_id),
                    'ordered_qty': float(qty),
                    'unit_cost_cents': int(float(cost) * 100)
                })
                
    if not items_data:
        flash('Cannot create purchase order with no items', 'error')
        return redirect(url_for('inventory.index', active_tab='purchasing'))
        
    try:
        inventory_service.create_purchase_order(
            branch_id=current_user.branch_id,
            supplier_id=supplier_id,
            items=items_data,
            expected_at=expected_at,
            notes=notes,
            created_by=current_user.employee_id
        )
        flash('Supplier order created successfully', 'success')
    except Exception as e:
        flash(str(e), 'error')
        
    return redirect(url_for('inventory.index', active_tab='purchasing'))


@inventory_bp.route('/purchase-orders/<int:id>', methods=['GET'])
@login_required
@permission_required('purchasing', 'view')
def get_po_details(id):
    try:
        po = inventory_service.get_purchase_order_summary(id)
        if po.branch_id != current_user.branch_id:
            return {'error': 'Unauthorized'}, 403
            
        items = []
        for item in po.items:
            items.append({
                'purchase_order_item_id': item.purchase_order_item_id,
                'ingredient_id': item.ingredient_id,
                'ingredient_name': item.ingredient.name,
                'unit': item.ingredient.unit,
                'ordered_qty': float(item.ordered_qty),
                'received_qty': float(item.received_qty),
                'unit_cost': float(item.unit_cost_cents / 100.0),
                'line_total': float(item.line_total_cents / 100.0),
                'notes': item.notes
            })
            
        return {
            'purchase_order_id': po.purchase_order_id,
            'po_number': po.po_number,
            'supplier_name': po.supplier.name,
            'status': po.status,
            'created_by_name': po.creator.full_name if po.creator else 'System/Unknown',
            'approved_by_name': po.approver.full_name if po.approver else 'N/A',
            'received_by_name': po.receiver.full_name if po.receiver else 'N/A',
            'created_at': po.created_at.strftime('%Y-%m-%d %H:%M') if po.created_at else 'N/A',
            'approved_at': po.approved_at.strftime('%Y-%m-%d %H:%M') if po.approved_at else 'N/A',
            'ordered_at': po.ordered_at.strftime('%Y-%m-%d %H:%M') if po.ordered_at else 'N/A',
            'expected_at': po.expected_at.strftime('%Y-%m-%d') if po.expected_at else 'N/A',
            'received_at': po.received_at.strftime('%Y-%m-%d %H:%M') if po.received_at else 'N/A',
            'notes': po.notes,
            'invoice_ref': po.invoice_ref or 'N/A',
            'items': items
        }
    except Exception as e:
        return {'error': str(e)}, 400


@inventory_bp.route('/purchase-orders/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('purchasing', 'approve')
def approve_po(id):
    try:
        inventory_service.approve_purchase_order(id, current_user.employee_id)
        flash('Supplier order approved', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('inventory.index', active_tab='purchasing'))


@inventory_bp.route('/purchase-orders/<int:id>/receive', methods=['POST'])
@login_required
@permission_required('purchasing', 'edit')
def receive_po(id):
    from datetime import datetime
    
    invoice_ref = request.form.get('invoice_ref')
    received_items = []
    
    item_ids = []
    for key in request.form.keys():
        if key.startswith('received_qty_'):
            item_ids.append(int(key.replace('received_qty_', '')))
            
    for item_id in item_ids:
        qty_str = request.form.get(f'received_qty_{item_id}')
        cost_str = request.form.get(f'actual_unit_cost_{item_id}')
        expiry_str = request.form.get(f'expiry_date_{item_id}')
        ref = request.form.get(f'supplier_ref_{item_id}')
        notes = request.form.get(f'notes_{item_id}')
        
        qty = float(qty_str or 0)
        cost = float(cost_str or 0)
        
        expiry_date = None
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d')
            except ValueError:
                pass
                
        received_items.append({
            'purchase_order_item_id': item_id,
            'received_qty': qty,
            'actual_unit_cost_cents': int(cost * 100),
            'expiry_date': expiry_date,
            'supplier_ref': ref,
            'notes': notes
        })
        
    if not received_items:
        flash('No items received', 'error')
        return redirect(url_for('inventory.index', active_tab='purchasing'))
        
    try:
        inventory_service.receive_purchase_order(
            po_id=id,
            received_items=received_items,
            invoice_ref=invoice_ref,
            received_by=current_user.employee_id
        )
        flash('Delivery received and stock updated', 'success')
    except Exception as e:
        flash(str(e), 'error')
        
    return redirect(url_for('inventory.index', active_tab='purchasing'))


@inventory_bp.route('/purchase-orders/<int:id>/cancel', methods=['POST'])
@login_required
@permission_required('purchasing', 'edit')
def cancel_po(id):
    reason = request.form.get('reason', 'Cancelled by manager')
    try:
        inventory_service.cancel_purchase_order(id, reason, current_user.employee_id)
        flash('Supplier order cancelled', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('inventory.index', active_tab='purchasing'))


@inventory_bp.route('/ingredients/add', methods=['POST'])
@login_required
@permission_required('inventory', 'create')
def add_ingredient_route():
    from app.models import Supplier
    import os
    import time
    from werkzeug.utils import secure_filename
    from flask import current_app
    
    suppliers = Supplier.query.all()
    form = IngredientForm(request.form)
    form.default_supplier_id.choices = [(0, 'Select Supplier')] + [(s.supplier_id, s.name) for s in suppliers]
    if form.validate():
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                upload_dir = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
                image_path = f"img/uploads/{filename}"

        try:
            supplier_id = form.default_supplier_id.data
            if supplier_id == 0:
                supplier_id = None
                
            inventory_service.create_ingredient(
                name=form.name.data,
                unit=form.unit.data,
                reorder_level=float(form.reorder_level.data),
                default_supplier_id=supplier_id,
                current_qty=float(form.current_qty.data or 0.0),
                branch_id=current_user.branch_id,
                image_path=image_path or form.image_path.data
            )
            flash('Ingredient added successfully', 'success')
        except Exception as e:
            flash(str(e), 'error')
    else:
        for field, errors in form.errors.items():
            flash(f"{field}: {', '.join(errors)}", 'error')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/ingredients/<int:id>/edit', methods=['POST'])
@login_required
@permission_required('inventory', 'edit')
def edit_ingredient_route(id):
    from app.models import Supplier
    import os
    import time
    from werkzeug.utils import secure_filename
    from flask import current_app
    
    suppliers = Supplier.query.all()
    form = IngredientForm(request.form)
    form.default_supplier_id.choices = [(0, 'Select Supplier')] + [(s.supplier_id, s.name) for s in suppliers]
    if form.validate():
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                upload_dir = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
                image_path = f"img/uploads/{filename}"

        try:
            supplier_id = form.default_supplier_id.data
            if supplier_id == 0:
                supplier_id = None
                
            update_data = {
                'ingredient_id': id,
                'name': form.name.data,
                'unit': form.unit.data,
                'reorder_level': float(form.reorder_level.data),
                'default_supplier_id': supplier_id,
                'is_active': int(form.is_active.data)
            }
            if image_path:
                update_data['image_path'] = image_path
            elif form.image_path.data:
                update_data['image_path'] = form.image_path.data
                
            inventory_service.update_ingredient(**update_data)
            flash('Ingredient updated successfully', 'success')
        except Exception as e:
            flash(str(e), 'error')
    else:
        for field, errors in form.errors.items():
            flash(f"{field}: {', '.join(errors)}", 'error')
    return redirect(url_for('inventory.index'))


@inventory_bp.route('/ingredients/<int:id>/history', methods=['GET'])
@login_required
@permission_required('inventory', 'view')
def get_ingredient_history_route(id):
    try:
        history = inventory_service.get_ingredient_history(id)
        return success_response(history)
    except Exception as e:
        return {'error': str(e)}, 400
