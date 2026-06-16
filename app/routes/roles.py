from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.decorators import permission_required, role_required
from app.models import Role, Permission, Employee, AuditLog, Branch
from extensions import db

roles_bp = Blueprint('roles', __name__, url_prefix='/admin/roles')


@roles_bp.route('', methods=['GET'])
@login_required
@permission_required('roles', 'manage')
def index():
    roles = Role.query.order_by(Role.is_system_role.desc(), Role.role_name).all()
    permissions = Permission.query.order_by(Permission.module, Permission.action).all()
    
    # Group permissions by module to make it clean in UI
    grouped_permissions = {}
    for p in permissions:
        grouped_permissions.setdefault(p.module, []).append(p)
        
    employees = Employee.query.filter_by(branch_id=current_user.branch_id).all()
    branches = Branch.query.filter_by(is_active=1).all()
    
    return render_template(
        'admin/roles.html',
        roles=roles,
        grouped_permissions=grouped_permissions,
        employees=employees,
        branches=branches,
        modules=['dashboard', 'pos', 'inventory', 'suppliers', 'purchasing', 'reports', 'settings'],
        actions=['view', 'create', 'edit', 'approve', 'delete', 'export']
    )


@roles_bp.route('/add', methods=['POST'])
@login_required
@permission_required('roles', 'manage')
def add_role():
    name = request.form.get('role_name')
    description = request.form.get('description')
    
    if not name:
        flash('Role name is required', 'danger')
        return redirect(url_for('roles.index'))
        
    existing = Role.query.filter_by(role_name=name).first()
    if existing:
        flash(f'Role "{name}" already exists', 'danger')
        return redirect(url_for('roles.index'))
        
    try:
        role = Role(role_name=name, description=description, is_system_role=0)
        db.session.add(role)
        db.session.commit()
        
        # Log to audit log
        audit = AuditLog(
            table_name='roles',
            record_id=role.role_id,
            action='INSERT',
            changed_by=current_user.employee_id,
            new_values=f"role_name={name}, description={description}"
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'Role "{name}" created successfully. You can now edit its permissions.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating role: {str(e)}', 'danger')
        
    return redirect(url_for('roles.index'))


@roles_bp.route('/<int:id>/edit', methods=['POST'])
@login_required
@permission_required('roles', 'manage')
def edit_role(id):
    role = db.session.get(Role, id)
    if not role:
        abort(404)
        
    # Owner / Admin role should always have full permissions (system protected)
    if role.role_name == 'Owner / Admin':
        flash('Permissions for the Owner / Admin role cannot be modified', 'danger')
        return redirect(url_for('roles.index'))
        
    name = request.form.get('role_name')
    description = request.form.get('description', '')
    
    # Only allow renaming non-system roles
    if role.is_system_role == 0 and name:
        old_name = role.role_name
        role.role_name = name
    else:
        name = role.role_name
        
    role.description = description
    
    # Process permissions checkboxes
    perm_ids = request.form.getlist('permissions')
    selected_perms = []
    for pid in perm_ids:
        p = db.session.get(Permission, int(pid))
        if p:
            selected_perms.append(p)
            
    old_perms = ", ".join([p.permission_key for p in role.permissions])
    role.permissions = selected_perms
    new_perms = ", ".join([p.permission_key for p in selected_perms])
    
    try:
        # Log to audit log
        audit = AuditLog(
            table_name='roles',
            record_id=role.role_id,
            action='UPDATE',
            changed_by=current_user.employee_id,
            old_values=f"description={role.description}, permissions=[{old_perms}]",
            new_values=f"description={description}, permissions=[{new_perms}]"
        )
        db.session.add(audit)
        db.session.commit()
        flash(f'Role "{role.role_name}" updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating role: {str(e)}', 'danger')
        
    return redirect(url_for('roles.index'))


@roles_bp.route('/<int:id>/duplicate', methods=['POST'])
@login_required
@permission_required('roles', 'manage')
def duplicate_role(id):
    source_role = db.session.get(Role, id)
    if not source_role:
        abort(404)
        
    name = f"Copy of {source_role.role_name}"
    # Ensure name uniqueness
    suffix = 1
    while Role.query.filter_by(role_name=name).first():
        name = f"Copy of {source_role.role_name} ({suffix})"
        suffix += 1
        
    try:
        new_role = Role(
            role_name=name,
            description=f"Duplicate of {source_role.role_name}. {source_role.description or ''}",
            is_system_role=0
        )
        # Duplicate permissions relationship
        new_role.permissions = list(source_role.permissions)
        db.session.add(new_role)
        db.session.commit()
        
        # Log to audit log
        audit = AuditLog(
            table_name='roles',
            record_id=new_role.role_id,
            action='INSERT',
            changed_by=current_user.employee_id,
            new_values=f"role_name={name}, duplicate_of={source_role.role_name}"
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'Role duplicated as "{name}" successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error duplicating role: {str(e)}', 'danger')
        
    return redirect(url_for('roles.index'))


@roles_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('roles', 'manage')
def delete_role(id):
    role = db.session.get(Role, id)
    if not role:
        abort(404)
        
    if role.is_system_role == 1:
        flash('System default roles cannot be deleted', 'danger')
        return redirect(url_for('roles.index'))
        
    # Verify if any user is currently assigned to this role
    assigned_users = Employee.query.filter_by(role_id=role.role_id).count()
    if assigned_users > 0:
        flash(f'Cannot delete role. There are {assigned_users} employee(s) currently assigned to this role. Reassign them first.', 'danger')
        return redirect(url_for('roles.index'))
        
    try:
        name = role.role_name
        # Delete mappings
        role.permissions = []
        db.session.delete(role)
        
        # Log to audit log
        audit = AuditLog(
            table_name='roles',
            record_id=id,
            action='DELETE',
            changed_by=current_user.employee_id,
            old_values=f"role_name={name}"
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'Role "{name}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting role: {str(e)}', 'danger')
        
    return redirect(url_for('roles.index'))


@roles_bp.route('/assign-user', methods=['POST'])
@login_required
@permission_required('roles', 'manage')
def assign_user():
    employee_id = request.form.get('employee_id', type=int)
    role_id = request.form.get('role_id', type=int)
    
    emp = db.session.get(Employee, employee_id)
    role = db.session.get(Role, role_id)
    
    if not emp or not role:
        flash('Invalid employee or role selected', 'danger')
        return redirect(url_for('roles.index'))
        
    if emp.branch_id != current_user.branch_id:
        flash('Unauthorized branch modification', 'danger')
        return redirect(url_for('roles.index'))
        
    try:
        old_role_name = emp.role_rel.role_name if emp.role_rel else 'None'
        emp.role_id = role.role_id
        
        # Log to audit log
        audit = AuditLog(
            table_name='employees',
            record_id=emp.employee_id,
            action='UPDATE',
            changed_by=current_user.employee_id,
            old_values=f"role_name={old_role_name}",
            new_values=f"role_name={role.role_name}"
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'Role for {emp.full_name} updated to "{role.role_name}" successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error assigning role: {str(e)}', 'danger')
        
    return redirect(url_for('roles.index'))
