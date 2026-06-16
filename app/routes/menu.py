from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app.decorators import role_required
from app.models import Category, MenuItem, Modifier
from app.utils.response import success_response
from extensions import db

menu_bp = Blueprint('menu', __name__, url_prefix='/menu')


@menu_bp.before_request
@login_required
@role_required('admin', 'manager')
def limit_menu_access():
    pass


@menu_bp.route('', methods=['GET'])
@login_required
@role_required('admin', 'manager')
def index():
    """Menu management page — passes categories, items, modifiers to template."""
    categories = Category.query.filter_by(is_active=1).order_by(Category.display_order).all()
    items = MenuItem.query.filter_by(is_active=1).all()
    modifiers = Modifier.query.filter_by(is_active=1).all()
    return render_template('admin/menu.html',
                           categories=categories,
                           items=items,
                           modifiers=modifiers)


@menu_bp.route('/categories', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def create_category():
    """Creates a new menu category."""
    name = request.form.get('name')
    if name:
        import os
        import time
        from werkzeug.utils import secure_filename
        from flask import current_app

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

        cat = Category(name=name, image_path=image_path, is_active=1)
        db.session.add(cat)
        db.session.commit()
        flash('Category created', 'success')
    return redirect(url_for('menu.index'))


@menu_bp.route('/categories/<int:id>/edit', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def edit_category(id):
    """Edits an existing category."""
    cat = db.session.get(Category, id)
    if cat is None: abort(404)
    cat.name = request.form.get('name', cat.name)
    
    import os
    import time
    from werkzeug.utils import secure_filename
    from flask import current_app
    
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"{int(time.time())}_{filename}"
            upload_dir = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            cat.image_path = f"img/uploads/{filename}"
            
    db.session.commit()
    flash('Category updated', 'success')
    return redirect(url_for('menu.index'))


@menu_bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_category(id):
    """Soft-deletes a category."""
    cat = db.session.get(Category, id)
    if cat is None: abort(404)
    cat.is_active = 0
    db.session.commit()
    flash('Category removed', 'success')
    return redirect(url_for('menu.index'))


@menu_bp.route('/items', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def create_item():
    """Creates a new menu item."""
    from app.utils.money import display_to_cents
    name = request.form.get('name')
    category_id = request.form.get('category_id', type=int)
    price = request.form.get('price')
    if name and category_id and price:
        import os
        import time
        from werkzeug.utils import secure_filename
        from flask import current_app

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

        item = MenuItem(
            name=name,
            category_id=category_id,
            price_cents=display_to_cents(price),
            branch_id=current_user.branch_id,
            image_path=image_path,
            is_active=1,
            is_available=1
        )
        db.session.add(item)
        db.session.commit()
        flash('Item created', 'success')
    return redirect(url_for('menu.index'))


@menu_bp.route('/items/<int:id>/edit', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def edit_item(id):
    """Edits an existing menu item."""
    from app.utils.money import display_to_cents
    item = db.session.get(MenuItem, id)
    if item is None: abort(404)
    item.name = request.form.get('name', item.name)
    price = request.form.get('price')
    if price:
        item.price_cents = display_to_cents(price)
    cat_id = request.form.get('category_id', type=int)
    if cat_id:
        item.category_id = cat_id

    import os
    import time
    from werkzeug.utils import secure_filename
    from flask import current_app

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"{int(time.time())}_{filename}"
            upload_dir = os.path.join(current_app.root_path, 'static', 'img', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            item.image_path = f"img/uploads/{filename}"

    db.session.commit()
    flash('Item updated', 'success')
    return redirect(url_for('menu.index'))


@menu_bp.route('/items/<int:id>/toggle', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def toggle_item(id):
    """Toggles item availability."""
    item = db.session.get(MenuItem, id)
    if item is None: abort(404)
    item.is_available = 0 if item.is_available else 1
    db.session.commit()
    return success_response({'is_available': item.is_available})


@menu_bp.route('/items/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_item(id):
    """Soft-deletes a menu item."""
    item = db.session.get(MenuItem, id)
    if item is None: abort(404)
    item.is_active = 0
    db.session.commit()
    flash('Item removed', 'success')
    return redirect(url_for('menu.index'))


@menu_bp.route('/modifiers', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def create_modifier():
    """Creates a new modifier."""
    from app.utils.money import display_to_cents
    name = request.form.get('name')
    price = request.form.get('price', '0')
    group = request.form.get('group_name', '')
    if name:
        mod = Modifier(name=name, price_cents=display_to_cents(price), group_name=group, is_active=1)
        db.session.add(mod)
        db.session.commit()
    return success_response()


@menu_bp.route('/api/categories', methods=['GET'])
@login_required
def api_categories():
    """Returns categories as JSON for AJAX consumers."""
    cats = Category.query.filter_by(is_active=1).order_by(Category.display_order).all()
    return success_response([{
        'category_id': c.category_id,
        'name': c.name,
        'item_count': len(c.items)
    } for c in cats])


@menu_bp.route('/public', methods=['GET'])
@menu_bp.route('/public/<int:table_number>', methods=['GET'])
def public_menu(table_number=None):
    """Public-facing menu for QR code scanning. No login required."""
    categories = Category.query.filter_by(is_active=1).order_by(Category.display_order).all()
    items = MenuItem.query.filter_by(is_active=1, is_available=1).all()
    return render_template('app/public_menu.html',
                           categories=categories,
                           items=items,
                           table_number=table_number)
