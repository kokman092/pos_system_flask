from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.decorators import permission_required
from app.services.report_service import dashboard_bundle
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard', methods=['GET'])
@login_required
@permission_required('dashboard', 'view')
def dashboard():
    try:
        data = dashboard_bundle(current_user.branch_id)
        # Inject server-side time info for greeting
        now = datetime.utcnow()
        data['server_hour'] = now.hour
        data['today_label'] = now.strftime('%A, %B %d, %Y')
        return render_template('admin/dashboard.html', bundle=data)
    except Exception as e:
        return render_template('admin/dashboard.html', error=str(e))

@dashboard_bp.route('/dashboard/api/live', methods=['GET'])
@login_required
@permission_required('dashboard', 'view')
def live():
    """Lightweight JSON endpoint for live dashboard auto-refresh."""
    try:
        from app.models import Order, OrderItem
        open_orders = Order.query.filter_by(
            branch_id=current_user.branch_id, status='open'
        ).count()
        kitchen_orders = Order.query.filter_by(
            branch_id=current_user.branch_id, status='open'
        ).join(
            OrderItem, Order.order_id == OrderItem.order_id
        ).filter(OrderItem.status == 'kitchen').distinct().count()
        return jsonify({
            'success': True,
            'data': {
                'open_orders': open_orders,
                'kitchen_orders': kitchen_orders
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/', methods=['GET'])
def index():
    return redirect(url_for('dashboard.dashboard'))
