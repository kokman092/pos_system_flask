from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from app.decorators import role_required
from app.models import RestaurantTable
from extensions import db

tables_bp = Blueprint('tables', __name__, url_prefix='/admin/tables')


@tables_bp.before_request
@login_required
@role_required('admin', 'manager')
def limit_tables_access():
    pass


@tables_bp.route('', methods=['GET'])
@login_required
def index():
    """Tables management dashboard."""
    tables = RestaurantTable.query.filter_by(
        branch_id=current_user.branch_id
    ).order_by(RestaurantTable.table_number).all()
    
    response = make_response(render_template('admin/tables.html', tables=tables))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@tables_bp.route('/save', methods=['POST'])
@login_required
def save_table():
    """Creates or updates a restaurant table config."""
    table_id = request.form.get('table_id', type=int)
    table_number = request.form.get('table_number')
    capacity = request.form.get('capacity', 4, type=int)
    status = request.form.get('status', 'available')
    location = request.form.get('location')
    is_active = request.form.get('is_active', 1, type=int)

    if not table_number:
        flash('Table number is required', 'error')
        return redirect(url_for('tables.index'))

    if table_id:
        # Update
        t = db.session.get(RestaurantTable, table_id)
        if t and t.branch_id == current_user.branch_id:
            t.table_number = table_number
            t.capacity = capacity
            t.status = status
            t.location = location if location else None
            t.is_active = is_active
            db.session.commit()
            flash('Table updated successfully', 'success')
    else:
        # Create
        existing = RestaurantTable.query.filter_by(
            branch_id=current_user.branch_id,
            table_number=table_number
        ).first()
        if existing:
            flash(f'Table {table_number} already exists', 'error')
        else:
            t = RestaurantTable(
                branch_id=current_user.branch_id,
                table_number=table_number,
                capacity=capacity,
                status=status,
                location=location if location else None,
                is_active=is_active
            )
            db.session.add(t)
            db.session.commit()
            flash('Table added successfully', 'success')
    return redirect(url_for('tables.index'))


@tables_bp.route('/<int:id>/toggle-active', methods=['POST'])
@login_required
def toggle_table_active(id):
    """Toggles active status of a table."""
    t = db.session.get(RestaurantTable, id)
    if t and t.branch_id == current_user.branch_id:
        t.is_active = 0 if t.is_active == 1 else 1
        db.session.commit()
        status_text = 'activated' if t.is_active == 1 else 'deactivated'
        flash(f'Table {t.table_number} has been {status_text}', 'success')
    return redirect(url_for('tables.index'))
