from datetime import datetime, timedelta
import csv
import io
from flask import Blueprint, render_template, request, Response
from flask_login import login_required, current_user
from app.decorators import role_required, permission_required
from app.services import report_service
from app.utils.response import success_response, error_response

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


@reports_bp.before_request
@login_required
def limit_reports_access():
    if not (current_user.has_permission('reports', 'sales') or
            current_user.has_permission('reports', 'inventory') or
            current_user.has_permission('reports', 'purchasing')):
        return render_template('errors/403.html'), 403

@reports_bp.route('', methods=['GET'])
@login_required
@permission_required('reports', 'sales')
def index():
    try:
        date_str = request.args.get('date')
        if not date_str:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            
        period = request.args.get('period', 'daily')
        if period not in ['daily', 'weekly', 'monthly', 'yearly']:
            period = 'daily'
            
        daily = report_service.daily_summary(current_user.branch_id, date_str, period=period)
        morning = report_service.shift_report(current_user.branch_id, 'morning', date_str, period=period)
        afternoon = report_service.shift_report(current_user.branch_id, 'afternoon', date_str, period=period)
        night = report_service.shift_report(current_user.branch_id, 'night', date_str, period=period)
        low_stock = report_service.low_stock_report(current_user.branch_id)
        
        # Get start/end range of the period for filtering trends and popular items
        from app.services.report_service import _get_period_date_range, _get_target_date
        start_dt, end_dt = _get_period_date_range(_get_target_date(date_str), period)
        start_date_str = start_dt.strftime('%Y-%m-%d')
        end_date_str = (end_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        
        revenue_trend = report_service.revenue_by_period(current_user.branch_id, start_date=None, end_date=date_str, period=period)
        top_items = report_service.item_popularity(current_user.branch_id, start_date=start_date_str, end_date=end_date_str, limit=50)
        
        # Dashboard bundle — includes customer_snapshot + revenue_comparison
        dashboard = report_service.dashboard_bundle(current_user.branch_id)
        
        return render_template(
            'admin/reports.html',
            daily=daily,
            dashboard=dashboard,
            shifts={'morning': morning, 'afternoon': afternoon, 'night': night},
            low_stock=low_stock,
            revenue_trend=revenue_trend,
            top_items=top_items,
            selected_date=date_str,
            selected_period=period
        )
    except Exception as e:
        return render_template('admin/reports.html', error=str(e))

@reports_bp.route('/api/daily', methods=['GET'])
@login_required
def daily():
    try:
        date_str = request.args.get('date')
        period = request.args.get('period', 'daily')
        data = report_service.daily_summary(current_user.branch_id, date_str, period=period)
        
        # Format as CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["AURA POS - Daily/Period Summary Report"])
        writer.writerow(["Branch ID", current_user.branch_id])
        writer.writerow(["Target Date/Anchor", date_str or datetime.utcnow().strftime('%Y-%m-%d')])
        writer.writerow(["Period Type", period.upper()])
        writer.writerow([])
        
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Revenue ($)", f"{data['total_revenue_cents'] / 100:.2f}"])
        writer.writerow(["Total Orders", data['total_orders']])
        writer.writerow(["Average Order Value ($)", f"{data['avg_order_cents'] / 100:.2f}"])
        writer.writerow(["Total Customers (Covers)", data['total_customers']])
        writer.writerow(["Active Tables Count", data['active_tables']])
        writer.writerow(["Waste Cost ($)", f"{data['waste_cost_cents'] / 100:.2f}"])
        writer.writerow([])
        
        writer.writerow(["Payment Methods Breakdown"])
        writer.writerow(["Payment Method", "Transaction Count", "Total Amount ($)"])
        for pm in data['payment_methods']:
            writer.writerow([pm['method'].replace('_', ' ').capitalize(), pm['count'], f"{pm['total_cents'] / 100:.2f}"])
            
        writer.writerow([])
        writer.writerow(["Top Selling Items"])
        writer.writerow(["Item Name", "Quantity Sold", "Revenue ($)"])
        for item in data['top_items']:
            writer.writerow([item['name'], item['qty_sold'], f"{item['revenue_cents'] / 100:.2f}"])
            
        response_data = output.getvalue()
        output.close()
        
        filename = f"summary_{period}_{date_str or 'today'}.csv"
        return Response(
            response_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/shift', methods=['GET'])
@login_required
def shift():
    try:
        date_str = request.args.get('date')
        period = request.args.get('period', 'daily')
        shift_name = request.args.get('shift', 'morning')
        return success_response(report_service.shift_report(current_user.branch_id, shift_name, date_str, period=period))
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/items', methods=['GET'])
@login_required
def items():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 50))
        
        data = report_service.item_popularity(
            current_user.branch_id,
            limit=limit,
            start_date=start_date,
            end_date=end_date
        )
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["AURA POS - Popular Items Report"])
        writer.writerow(["Branch ID", current_user.branch_id])
        writer.writerow(["Date Range", f"{start_date or 'Start'} to {end_date or 'End'}"])
        writer.writerow([])
        
        writer.writerow(["Item Name", "Category", "Quantity Sold", "Revenue ($)"])
        for item in data:
            writer.writerow([item['item_name'], item['category_name'], item['qty_sold'], f"{item['revenue_cents'] / 100:.2f}"])
            
        response_data = output.getvalue()
        output.close()
        
        filename = f"popular_items_{start_date or 'start'}_to_{end_date or 'end'}.csv"
        return Response(
            response_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/revenue', methods=['GET'])
@login_required
def revenue():
    try:
        period = request.args.get('period', 'daily')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        data = report_service.revenue_by_period(
            current_user.branch_id,
            start_date,
            end_date,
            period=period
        )
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["AURA POS - Revenue Trend Report"])
        writer.writerow(["Branch ID", current_user.branch_id])
        writer.writerow(["Reporting Period Type", period.upper()])
        writer.writerow(["Date Range", f"{start_date or 'Start'} to {end_date or 'End'}"])
        writer.writerow([])
        
        writer.writerow(["Period Key (Date/Week/Month/Year)", "Revenue ($)", "Order Count"])
        for item in data:
            writer.writerow([item['date'], f"{item['revenue_cents'] / 100:.2f}", item['order_count']])
            
        response_data = output.getvalue()
        output.close()
        
        filename = f"revenue_trend_{period}_{start_date or 'start'}_to_{end_date or 'end'}.csv"
        return Response(
            response_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/payments', methods=['GET'])
@login_required
def payments():
    try:
        return success_response(report_service.payment_breakdown(current_user.branch_id, request.args.get('start_date'), request.args.get('end_date')))
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/inventory', methods=['GET'])
@login_required
def inventory():
    try:
        data = report_service.inventory_valuation(current_user.branch_id)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["AURA POS - Inventory Valuation Report"])
        writer.writerow(["Branch ID", current_user.branch_id])
        writer.writerow(["Total Stock Value ($)", f"{data['total_stock_value_cents'] / 100:.2f}"])
        writer.writerow([])
        
        writer.writerow(["Ingredient Name", "Quantity In Stock", "Unit", "Stock Value ($)"])
        for item in data['items']:
            writer.writerow([item['name'], item['qty_in_stock'], item['unit'], f"{item['stock_value_cents'] / 100:.2f}"])
            
        response_data = output.getvalue()
        output.close()
        
        filename = f"inventory_valuation_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
        return Response(
            response_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/waste', methods=['GET'])
@login_required
def waste():
    try:
        page = request.args.get('page', type=int)
        per_page = request.args.get('per_page', 50, type=int)
        return success_response(report_service.waste_report(
            current_user.branch_id,
            request.args.get('start_date'),
            request.args.get('end_date'),
            page=page,
            per_page=per_page
        ))
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/low-stock', methods=['GET'])
@login_required
def low_stock():
    try:
        return success_response(report_service.low_stock_report(current_user.branch_id))
    except Exception as e:
        return error_response(str(e))

@reports_bp.route('/api/categories', methods=['GET'])
@login_required
def categories():
    try:
        days = int(request.args.get('days', 30))
        return success_response(report_service.category_performance(current_user.branch_id, days=days))
    except Exception as e:
        return error_response(str(e))


# =========================================================================
# Production-Grade Export Endpoints
# =========================================================================

from app.services import export_service

def _parse_and_validate_dates(start_date_str, end_date_str, user_role):
    try:
        if not end_date_str:
            end_dt = datetime.utcnow().date()
        else:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
        if not start_date_str:
            start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError("Invalid date format. Expected YYYY-MM-DD")
        
    if start_dt > end_dt:
        raise ValueError("start_date cannot be after end_date")
        
    if (end_dt - start_dt).days > 90 and user_role != 'admin':
        raise ValueError("Ad-hoc export range exceeds 90 days threshold. Please contact an Administrator.")
        
    return start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d')


@reports_bp.route('/export/revenue.csv', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_revenue_csv():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        stream = export_service.export_revenue_csv(current_user.branch_id, start_date, end_date)
        filename = f"revenue_report_{start_date}_to_{end_date}.csv"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
        return Response(stream, headers=headers)
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/revenue.xlsx', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_revenue_xlsx():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        xlsx_bytes = export_service.export_revenue_xlsx(current_user.branch_id, start_date, end_date)
        filename = f"revenue_report_{start_date}_to_{end_date}.xlsx"
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/payments.csv', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_payments_csv():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        stream = export_service.export_payments_csv(current_user.branch_id, start_date, end_date)
        filename = f"payments_report_{start_date}_to_{end_date}.csv"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
        return Response(stream, headers=headers)
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/payments.xlsx', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_payments_xlsx():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        xlsx_bytes = export_service.export_payments_xlsx(current_user.branch_id, start_date, end_date)
        filename = f"payments_report_{start_date}_to_{end_date}.xlsx"
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/items.csv', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_items_csv():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        stream = export_service.export_items_csv(current_user.branch_id, start_date, end_date)
        filename = f"items_report_{start_date}_to_{end_date}.csv"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
        return Response(stream, headers=headers)
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/items.xlsx', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_items_xlsx():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        xlsx_bytes = export_service.export_items_xlsx(current_user.branch_id, start_date, end_date)
        filename = f"items_report_{start_date}_to_{end_date}.xlsx"
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/waste.csv', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_waste_csv():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        stream = export_service.export_waste_csv(current_user.branch_id, start_date, end_date)
        filename = f"waste_report_{start_date}_to_{end_date}.csv"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
        return Response(stream, headers=headers)
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/waste.xlsx', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_waste_xlsx():
    try:
        start_date, end_date = _parse_and_validate_dates(
            request.args.get('start_date'),
            request.args.get('end_date'),
            current_user.role
        )
        xlsx_bytes = export_service.export_waste_xlsx(current_user.branch_id, start_date, end_date)
        filename = f"waste_report_{start_date}_to_{end_date}.xlsx"
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/inventory.csv', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_inventory_csv():
    try:
        stream = export_service.export_inventory_csv(current_user.branch_id)
        filename = f"inventory_valuation_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
        return Response(stream, headers=headers)
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/inventory.xlsx', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_inventory_xlsx():
    try:
        xlsx_bytes = export_service.export_inventory_xlsx(current_user.branch_id)
        filename = f"inventory_valuation_{datetime.utcnow().strftime('%Y-%m-%d')}.xlsx"
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/daily.pdf', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_daily_pdf():
    try:
        date_str = request.args.get('date')
        if not date_str:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
        pdf_bytes = export_service.export_daily_pdf(current_user.branch_id, date_str)
        filename = f"daily_report_{date_str}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))


@reports_bp.route('/export/shift.pdf', methods=['GET'])
@login_required
@permission_required('reports', 'export')
def export_shift_pdf():
    try:
        date_str = request.args.get('date')
        if not date_str:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
        shift_name = request.args.get('shift', 'morning')
        if shift_name not in ['morning', 'afternoon', 'night']:
            shift_name = 'morning'
        pdf_bytes = export_service.export_shift_pdf(current_user.branch_id, shift_name, date_str)
        filename = f"shift_report_{shift_name}_{date_str}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return error_response(str(e))
