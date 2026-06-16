from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.decorators import role_required
from app.forms.employee_forms import InviteEmployeeForm, EditEmployeeForm, ChangeRoleForm
from app.models import Employee, Branch
from app.services import auth_service
from extensions import db

employees_bp = Blueprint('employees', __name__, url_prefix='/admin/employees')


@employees_bp.before_request
@login_required
@role_required('admin', 'manager')
def limit_employees_access():
    pass


@employees_bp.route('', methods=['GET'])
@login_required
@role_required('admin', 'manager')
def index():
    """Employee management page — passes employees for current branch."""
    from app.models import Role
    roles_list = Role.query.order_by(Role.role_name).all()
    
    invite_form = InviteEmployeeForm()
    invite_form.branch_id.choices = [
        (b.branch_id, b.name) 
        for b in Branch.query.filter_by(is_active=1).all()
    ]
    invite_form.role_id.choices = [(r.role_id, r.role_name) for r in roles_list]
    
    edit_form = EditEmployeeForm()
    edit_form.role_id.choices = [(r.role_id, r.role_name) for r in roles_list]
    
    employees = Employee.query.filter_by(
        branch_id=current_user.branch_id
    ).order_by(Employee.full_name).all()
    branches = Branch.query.filter_by(is_active=1).all()
    return render_template('admin/employees.html',
                           employees=employees,
                           branches=branches,
                           invite_form=invite_form,
                           edit_form=edit_form,
                           roles_list=roles_list)


@employees_bp.route('/invite', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def invite():
    """Registers a new employee."""
    form = InviteEmployeeForm()
    form.branch_id.choices = [
        (b.branch_id, b.name) 
        for b in Branch.query.filter_by(is_active=1).all()
    ]
    from app.models import Role
    form.role_id.choices = [
        (r.role_id, r.role_name)
        for r in Role.query.order_by(Role.role_name).all()
    ]
    
    if form.validate_on_submit():
        try:
            employee = auth_service.register_employee(
                branch_id=form.branch_id.data,
                full_name=form.full_name.data,
                role=form.role_id.data,
                email=form.email.data,
                password=form.password.data,
                created_by_admin=True  # skip email verification
            )
            flash(
                f"Employee '{employee.full_name}' created successfully. "
                f"They can now login with their email and password.",
                "success"
            )
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            db.session.rollback()
            flash("Failed to create employee. Please try again.", "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for('employees.index'))


@employees_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def edit(id):
    """Edits employee details."""
    emp = db.session.get(Employee, id)
    if emp is None: abort(404)
    if emp.branch_id != current_user.branch_id:
        flash('Access denied', 'error')
        return redirect(url_for('employees.index'))
    emp.full_name = request.form.get('full_name', emp.full_name)
    db.session.commit()
    flash('Employee updated', 'success')
    return redirect(url_for('employees.index'))


@employees_bp.route('/<int:id>/role', methods=['POST'])
@login_required
@role_required('admin')
def role(id):
    """Changes an employee's role (admin only)."""
    form = ChangeRoleForm(request.form)
    from app.models import Role
    form.new_role_id.choices = [
        (r.role_id, r.role_name)
        for r in Role.query.order_by(Role.role_name).all()
    ]
    if form.validate():
        try:
            auth_service.change_role(id, form.new_role_id.data, current_user.employee_id)
            flash('Role updated', 'success')
        except Exception as e:
            flash(str(e), 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for('employees.index'))


@employees_bp.route('/<int:id>/deactivate', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def deactivate(id):
    """Soft-deactivates an employee."""
    emp = db.session.get(Employee, id)
    if emp is None: abort(404)
    if emp.branch_id != current_user.branch_id:
        flash('Access denied', 'error')
        return redirect(url_for('employees.index'))
    emp.is_active = 0
    db.session.commit()
    flash('Employee deactivated', 'success')
    return redirect(url_for('employees.index'))
