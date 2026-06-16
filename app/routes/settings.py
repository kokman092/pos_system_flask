from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.decorators import role_required, permission_required
from app.models import PrinterConfig, Branch
from app.utils.response import success_response
from extensions import db

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.before_request
@login_required
@permission_required('settings', 'manage')
def limit_settings_access():
    pass


@settings_bp.route('', methods=['GET'])
@login_required
@permission_required('settings', 'manage')
def index():
    """Settings page — passes printers and branch info."""
    printers = PrinterConfig.query.filter_by(
        branch_id=current_user.branch_id
    ).all()
    branch = db.session.get(Branch, current_user.branch_id)
    return render_template('admin/settings.html',
                           printers=printers,
                           branch=branch)


@settings_bp.route('/printer', methods=['POST'])
@login_required
@permission_required('settings', 'manage')
def printer():
    """Creates or updates a printer config."""
    name = request.form.get('name')
    ip = request.form.get('ip_address')
    port = request.form.get('port', 9100, type=int)
    role = request.form.get('printer_role', 'receipt')
    if name and ip:
        p = PrinterConfig(
            branch_id=current_user.branch_id,
            name=name,
            ip_address=ip,
            port=port,
            printer_role=role,
            is_enabled=1
        )
        db.session.add(p)
        db.session.commit()
        flash('Printer added', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/printer/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('settings', 'manage')
def delete_printer(id):
    """Deletes a printer config."""
    p = db.session.get(PrinterConfig, id)
    if p is None: abort(404)
    if p.branch_id != current_user.branch_id:
        flash('Access denied', 'error')
        return redirect(url_for('settings.index'))
    db.session.delete(p)
    db.session.commit()
    flash('Printer removed', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/printer/<int:id>/test', methods=['POST'])
@login_required
@permission_required('settings', 'manage')
def test_printer(id):
    """Tests a printer connection."""
    from app.services.printer_service import test_connection
    p = db.session.get(PrinterConfig, id)
    if p is None: abort(404)
    if p.branch_id != current_user.branch_id:
        return success_response({'status': 'error', 'message': 'Access denied'})
    
    success, message = test_connection(p.ip_address, p.port)
    if success:
        return success_response({'status': 'success', 'message': message})
    else:
        return success_response({'status': 'error', 'message': message})


@settings_bp.route('/branch', methods=['POST'])
@login_required
@permission_required('settings', 'manage')
def branch():
    """Updates branch settings."""
    b = db.session.get(Branch, current_user.branch_id)
    if b:
        b.name = request.form.get('name', b.name)
        b.location = request.form.get('location', b.location)
        b.phone = request.form.get('phone', b.phone)
        db.session.commit()
        flash('Branch settings updated', 'success')
    return redirect(url_for('settings.index'))



