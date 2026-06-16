from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date, extract
from extensions import db
from app.models import (
    Order, OrderItem, Payment, RestaurantTable, MenuItem,
    Category, Ingredient, WasteLog
)

_dashboard_cache = {}

def _get_target_date(date_str):
    if date_str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    return datetime.utcnow().date()

def _get_period_date_range(target_date, period='daily'):
    if period == 'weekly':
        # Start on Monday of that week
        start_day = target_date - timedelta(days=target_date.weekday())
        start = datetime(start_day.year, start_day.month, start_day.day)
        end = start + timedelta(days=7)
    elif period == 'monthly':
        start = datetime(target_date.year, target_date.month, 1)
        if target_date.month == 12:
            end = datetime(target_date.year + 1, 1, 1)
        else:
            end = datetime(target_date.year, target_date.month + 1, 1)
    elif period == 'yearly':
        start = datetime(target_date.year, 1, 1)
        end = datetime(target_date.year + 1, 1, 1)
    else: # daily
        start = datetime(target_date.year, target_date.month, target_date.day)
        end = start + timedelta(days=1)
    return start, end

def _get_date_range(target_date):
    return _get_period_date_range(target_date, 'daily')

def daily_summary(branch_id: int, date=None, period='daily') -> dict:
    target_date = _get_target_date(date)
    start_dt, end_dt = _get_period_date_range(target_date, period)
    
    # 1. Base Order Count and Revenue in one query (preventing duplicate order counting)
    summary = db.session.query(
        func.count(Order.order_id.distinct()).label('total_orders'),
        func.coalesce(func.sum(Payment.amount_cents), 0).label('total_revenue')
    ).join(Payment, Payment.order_id == Order.order_id)\
     .filter(
         Order.branch_id == branch_id,
         Order.status == 'paid',
         Order.opened_at >= start_dt,
         Order.opened_at < end_dt,
         Payment.is_voided == 0
     ).first()
     
    total_orders = summary.total_orders or 0
    total_revenue_cents = int(summary.total_revenue or 0)
    avg_order_cents = total_revenue_cents // total_orders if total_orders > 0 else 0
    
    # 2. Customers covers
    total_customers = db.session.query(
        func.coalesce(func.sum(Order.pax), 0)
    ).filter(
        Order.branch_id == branch_id,
        Order.status == 'paid',
        Order.opened_at >= start_dt,
        Order.opened_at < end_dt
    ).scalar() or 0
    
    # 3. Active Tables count
    active_tables = RestaurantTable.query.filter_by(branch_id=branch_id, status='occupied').count()
    
    # 4. Payments breakdown with zero defaults
    payment_methods_dict = {
        'cash': {"method": 'cash', "total_cents": 0, "count": 0},
        'card': {"method": 'card', "total_cents": 0, "count": 0},
        'qr_code': {"method": 'qr_code', "total_cents": 0, "count": 0}
    }
    
    pm_query = db.session.query(
        Payment.method,
        func.coalesce(func.sum(Payment.amount_cents), 0).label('total'),
        func.count(Payment.payment_id).label('count')
    ).join(Order, Payment.order_id == Order.order_id)\
     .filter(
         Order.branch_id == branch_id,
         Order.status == 'paid',
         Order.opened_at >= start_dt,
         Order.opened_at < end_dt,
         Payment.is_voided == 0
     ).group_by(Payment.method).all()
     
    for method, amt, count in pm_query:
        if method:
            payment_methods_dict[method] = {"method": method, "total_cents": int(amt or 0), "count": count}
            
    payment_methods = list(payment_methods_dict.values())
    
    # 5. Top 5 Items (No joins to payments to avoid row multiplication)
    top_query = db.session.query(
        MenuItem.name,
        func.sum(OrderItem.quantity).label('qty_sold'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price_cents), 0).label('revenue')
    ).join(OrderItem, MenuItem.item_id == OrderItem.item_id)\
     .join(Order, Order.order_id == OrderItem.order_id)\
     .filter(
         Order.branch_id == branch_id,
         Order.status == 'paid',
         Order.opened_at >= start_dt,
         Order.opened_at < end_dt,
         OrderItem.status != 'cancelled'
     ).group_by(MenuItem.item_id, MenuItem.name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(5).all()
     
    top_items = [{"name": name, "qty_sold": qty, "revenue_cents": int(rev or 0)} for name, qty, rev in top_query]
    
    # 6. Hourly Revenue
    try:
        hour_query = db.session.query(
            extract('hour', Order.opened_at).label('hour'),
            func.coalesce(func.sum(Payment.amount_cents), 0).label('revenue')
        ).join(Payment, Order.order_id == Payment.order_id)\
         .filter(
             Order.branch_id == branch_id,
             Order.status == 'paid',
             Order.opened_at >= start_dt,
             Order.opened_at < end_dt,
             Payment.is_voided == 0
         ).group_by(extract('hour', Order.opened_at))\
         .order_by('hour').all()
    except Exception:
        hour_query = db.session.query(
            func.strftime('%H', Order.opened_at).label('hour'),
            func.coalesce(func.sum(Payment.amount_cents), 0).label('revenue')
        ).join(Payment, Order.order_id == Payment.order_id)\
         .filter(
             Order.branch_id == branch_id,
             Order.status == 'paid',
             Order.opened_at >= start_dt,
             Order.opened_at < end_dt,
             Payment.is_voided == 0
         ).group_by(func.strftime('%H', Order.opened_at))\
         .order_by('hour').all()
         
    hourly_revenue = []
    for hr, amt in hour_query:
        if hr is not None:
            hourly_revenue.append({"hour": f"{int(hr)}:00", "revenue_cents": int(amt or 0)})
            
    low_stock_count = len(low_stock_report(branch_id))
    
    waste_cost = db.session.query(
        func.coalesce(func.sum(WasteLog.qty * WasteLog.unit_cost_cents), 0)
    ).filter(
        WasteLog.branch_id == branch_id,
        WasteLog.created_at >= start_dt,
        WasteLog.created_at < end_dt
    ).scalar() or 0
    
    return {
        "total_orders": total_orders,
        "total_revenue_cents": total_revenue_cents,
        "avg_order_cents": avg_order_cents,
        "total_customers": int(total_customers),
        "active_tables": active_tables,
        "payment_methods": payment_methods,
        "top_items": top_items,
        "hourly_revenue": hourly_revenue,
        "low_stock_count": low_stock_count,
        "waste_cost_cents": int(waste_cost)
    }

def shift_report(branch_id: int, shift: str, date=None, period='daily') -> dict:
    if period == 'daily':
        start_dt, end_dt = _get_date_range(_get_target_date(date))
        if shift == 'morning':
            end_dt = start_dt + timedelta(hours=12)
        elif shift == 'afternoon':
            start_dt = start_dt + timedelta(hours=12)
            end_dt = start_dt + timedelta(hours=6)
        elif shift == 'night':
            start_dt = start_dt + timedelta(hours=18)
            
        summary = db.session.query(
            func.count(Order.order_id.distinct()).label('total_orders'),
            func.coalesce(func.sum(Payment.amount_cents), 0).label('total_revenue')
        ).join(Payment, Payment.order_id == Order.order_id)\
         .filter(
             Order.branch_id == branch_id,
             Order.status == 'paid',
             Order.opened_at >= start_dt,
             Order.opened_at < end_dt,
             Payment.is_voided == 0
         ).first()
    else:
        start_dt, end_dt = _get_period_date_range(_get_target_date(date), period)
        
        def get_shift_query(hour_expr):
            q = db.session.query(
                func.count(Order.order_id.distinct()).label('total_orders'),
                func.coalesce(func.sum(Payment.amount_cents), 0).label('total_revenue')
            ).join(Payment, Payment.order_id == Order.order_id)\
             .filter(
                 Order.branch_id == branch_id,
                 Order.status == 'paid',
                 Order.opened_at >= start_dt,
                 Order.opened_at < end_dt,
                 Payment.is_voided == 0
             )
            if shift == 'morning':
                q = q.filter(hour_expr >= 0, hour_expr < 12)
            elif shift == 'afternoon':
                q = q.filter(hour_expr >= 12, hour_expr < 18)
            elif shift == 'night':
                q = q.filter(hour_expr >= 18, hour_expr < 24)
            return q.first()
            
        try:
            summary = get_shift_query(extract('hour', Order.opened_at))
        except Exception:
            summary = get_shift_query(cast(func.strftime('%H', Order.opened_at), db.Integer))
            
    return {
        "shift": shift,
        "total_orders": summary.total_orders or 0,
        "total_revenue_cents": int(summary.total_revenue or 0)
    }

def revenue_by_period(branch_id: int, start_date=None, end_date=None, page=None, per_page=20, period='daily'):
    if period == 'weekly':
        days_back = 7 * 7
    elif period == 'monthly':
        days_back = 11 * 30
    elif period == 'yearly':
        days_back = 4 * 365
    else:
        days_back = 13
        
    end_dt = _get_target_date(end_date) if end_date else datetime.utcnow().date()
    start_dt = _get_target_date(start_date) if start_date else (end_dt - timedelta(days=days_back))
    
    if start_date and end_date and (end_dt - start_dt).days > 90 and period == 'daily':
        raise ValueError("Date range cannot exceed 90 days")
        
    start_dt_full = datetime(start_dt.year, start_dt.month, start_dt.day)
    end_dt_full = datetime(end_dt.year, end_dt.month, end_dt.day) + timedelta(days=1)
    
    if db.engine.name == 'sqlite':
        if period == 'weekly':
            date_expr = func.strftime('%Y-W%W', Order.opened_at)
        elif period == 'monthly':
            date_expr = func.strftime('%Y-%m', Order.opened_at)
        elif period == 'yearly':
            date_expr = func.strftime('%Y', Order.opened_at)
        else:
            date_expr = func.date(Order.opened_at)
    else:
        if period == 'weekly':
            date_expr = func.to_char(Order.opened_at, 'YYYY-IW')
        elif period == 'monthly':
            date_expr = func.to_char(Order.opened_at, 'YYYY-MM')
        elif period == 'yearly':
            date_expr = func.to_char(Order.opened_at, 'YYYY')
        else:
            date_expr = cast(Order.opened_at, Date)

    query = db.session.query(
        date_expr.label('day'),
        func.coalesce(func.sum(Payment.amount_cents), 0).label('revenue'),
        func.count(Order.order_id.distinct()).label('orders'),
        func.min(Order.opened_at).label('min_date')
    ).join(Payment, Order.order_id == Payment.order_id)\
     .filter(
        Order.branch_id == branch_id,
        Order.status == 'paid',
        Order.opened_at >= start_dt_full,
        Order.opened_at < end_dt_full,
        Payment.is_voided == 0
    ).group_by(date_expr)\
     .order_by('day')
     
    if page:
        from app.utils.pagination import paginate_query
        paginated = paginate_query(query, page, per_page)
        paginated['items'] = [{"date": str(q.day), "revenue_cents": int(q.revenue), "order_count": q.orders} for q in paginated['items']]
        return paginated
    else:
        results = query.all()
        # Initialize padded dictionary covering the entire range
        trend_dict = {}
        curr = start_dt
        while curr <= end_dt:
            if period == 'weekly':
                key = curr.strftime('%Y-W%W')
            elif period == 'monthly':
                key = curr.strftime('%Y-%m')
            elif period == 'yearly':
                key = curr.strftime('%Y')
            else:
                key = curr.strftime('%Y-%m-%d')
            
            if key not in trend_dict:
                trend_dict[key] = {
                    "date": key,
                    "revenue_cents": 0,
                    "order_count": 0
                }
            curr += timedelta(days=1)
            
        # Merge database results into standard structure using robust formatted date matching
        for q in results:
            if q.min_date:
                if period == 'weekly':
                    db_key = q.min_date.strftime('%Y-W%W')
                elif period == 'monthly':
                    db_key = q.min_date.strftime('%Y-%m')
                elif period == 'yearly':
                    db_key = q.min_date.strftime('%Y')
                else:
                    db_key = q.min_date.strftime('%Y-%m-%d')
            else:
                db_key = str(q.day)
                
            if db_key in trend_dict:
                trend_dict[db_key]["revenue_cents"] = int(q.revenue)
                trend_dict[db_key]["order_count"] = q.orders
            else:
                trend_dict[db_key] = {
                    "date": db_key,
                    "revenue_cents": int(q.revenue),
                    "order_count": q.orders
                }
                
        sorted_keys = sorted(trend_dict.keys())
        return [trend_dict[k] for k in sorted_keys]

def item_popularity(branch_id: int, days=7, limit=50, start_date=None, end_date=None) -> list:
    if start_date or end_date:
        start_dt = _get_target_date(start_date) if start_date else (datetime.utcnow() - timedelta(days=7)).date()
        end_dt = _get_target_date(end_date) if end_date else datetime.utcnow().date()
        start_dt_full = datetime(start_dt.year, start_dt.month, start_dt.day)
        end_dt_full = datetime(end_dt.year, end_dt.month, end_dt.day) + timedelta(days=1)
    else:
        end_dt_full = datetime.utcnow()
        start_dt_full = end_dt_full - timedelta(days=min(days, 90))
        
    query = db.session.query(
        MenuItem.item_id,
        MenuItem.name.label('item_name'),
        Category.name.label('category_name'),
        func.sum(OrderItem.quantity).label('qty_sold'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price_cents), 0).label('revenue')
    ).join(OrderItem, MenuItem.item_id == OrderItem.item_id)\
     .join(Order, Order.order_id == OrderItem.order_id)\
     .join(Category, Category.category_id == MenuItem.category_id)\
     .filter(
        Order.branch_id == branch_id,
        Order.status == 'paid',
        Order.opened_at >= start_dt_full,
        Order.opened_at < end_dt_full,
        OrderItem.status != 'cancelled'
    ).group_by(MenuItem.item_id, MenuItem.name, Category.name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(limit)
     
    results = query.all()
    return [{"item_id": r.item_id, "item_name": r.item_name, "category_name": r.category_name, "qty_sold": r.qty_sold, "revenue_cents": int(r.revenue or 0)} for r in results]

def payment_breakdown(branch_id: int, start_date=None, end_date=None) -> list:
    start_dt = _get_target_date(start_date) if start_date else (datetime.utcnow() - timedelta(days=14)).date()
    end_dt = _get_target_date(end_date) if end_date else datetime.utcnow().date()
    
    start_dt_full = datetime(start_dt.year, start_dt.month, start_dt.day)
    end_dt_full = datetime(end_dt.year, end_dt.month, end_dt.day) + timedelta(days=1)
    
    payment_methods_dict = {
        'cash': {"method": 'cash', "transaction_count": 0, "total_cents": 0},
        'card': {"method": 'card', "transaction_count": 0, "total_cents": 0},
        'qr_code': {"method": 'qr_code', "transaction_count": 0, "total_cents": 0}
    }
    
    query = db.session.query(
        Payment.method,
        func.count(Payment.payment_id).label('count'),
        func.coalesce(func.sum(Payment.amount_cents), 0).label('total')
    ).join(Order, Payment.order_id == Order.order_id)\
     .filter(
        Order.branch_id == branch_id,
        Order.status == 'paid',
        Order.opened_at >= start_dt_full,
        Order.opened_at < end_dt_full,
        Payment.is_voided == 0
    ).group_by(Payment.method).all()
    
    for method, count, amt in query:
        if method:
            payment_methods_dict[method] = {"method": method, "transaction_count": count, "total_cents": int(amt or 0)}
            
    return list(payment_methods_dict.values())

def inventory_valuation(branch_id: int) -> dict:
    results = db.session.query(
        Ingredient.ingredient_id,
        Ingredient.name,
        Ingredient.unit,
        Ingredient.qty_in_stock,
        Ingredient.cost_per_unit_cents,
        (Ingredient.qty_in_stock * Ingredient.cost_per_unit_cents).label('stock_value_cents')
    ).filter(
        Ingredient.branch_id == branch_id,
        Ingredient.qty_in_stock > 0
    ).order_by(db.desc('stock_value_cents')).all()
    
    total = db.session.query(
        func.coalesce(func.sum(Ingredient.qty_in_stock * Ingredient.cost_per_unit_cents), 0)
    ).filter(Ingredient.branch_id == branch_id).scalar() or 0
    
    items = []
    for r in results:
        items.append({
            "ingredient_id": r.ingredient_id,
            "name": r.name,
            "qty_in_stock": float(r.qty_in_stock or 0),
            "unit": r.unit,
            "stock_value_cents": int(r.stock_value_cents or 0)
        })
        
    return {
        "total_stock_value_cents": int(total),
        "items": items
    }

def waste_report(branch_id: int, start_date=None, end_date=None, page=None, per_page=50):
    start_dt = _get_target_date(start_date) if start_date else (datetime.utcnow() - timedelta(days=30)).date()
    end_dt = _get_target_date(end_date) if end_date else datetime.utcnow().date()
    
    start_dt_full = datetime(start_dt.year, start_dt.month, start_dt.day)
    end_dt_full = datetime(end_dt.year, end_dt.month, end_dt.day) + timedelta(days=1)
    
    query = db.session.query(
        Ingredient.name.label('ingredient_name'),
        WasteLog.qty,
        WasteLog.reason,
        WasteLog.unit_cost_cents,
        (WasteLog.qty * WasteLog.unit_cost_cents).label('total_cost_cents'),
        WasteLog.created_at
    ).join(Ingredient, WasteLog.ingredient_id == Ingredient.ingredient_id)\
     .filter(
        WasteLog.branch_id == branch_id,
        WasteLog.created_at >= start_dt_full,
        WasteLog.created_at < end_dt_full
    ).order_by(WasteLog.created_at.desc())
    
    if page:
        from app.utils.pagination import paginate_query
        paginated = paginate_query(query, page, per_page)
        paginated['items'] = [{
            "ingredient_name": q.ingredient_name,
            "qty": float(q.qty or 0),
            "reason": q.reason,
            "unit_cost_cents": q.unit_cost_cents,
            "total_cost_cents": int(q.total_cost_cents or 0),
            "created_at": q.created_at.isoformat()
        } for q in paginated['items']]
        return paginated
    else:
        results = query.all()
        return [{
            "ingredient_name": q.ingredient_name,
            "qty": float(q.qty or 0),
            "reason": q.reason,
            "unit_cost_cents": q.unit_cost_cents,
            "total_cost_cents": int(q.total_cost_cents or 0),
            "created_at": q.created_at.isoformat()
        } for q in results]

def low_stock_report(branch_id: int) -> list:
    results = db.session.query(
        Ingredient.ingredient_id,
        Ingredient.name.label('ingredient_name'),
        Ingredient.unit,
        Ingredient.qty_in_stock,
        Ingredient.reorder_level,
        (Ingredient.reorder_level - Ingredient.qty_in_stock).label('shortage_qty')
    ).filter(
        Ingredient.branch_id == branch_id,
        Ingredient.qty_in_stock <= Ingredient.reorder_level
    ).order_by(db.desc('shortage_qty')).all()
    
    return [{
        "ingredient_name": r.ingredient_name,
        "qty_in_stock": float(r.qty_in_stock or 0),
        "reorder_level": float(r.reorder_level or 0),
        "shortage_qty": float(r.shortage_qty or 0)
    } for r in results]

def category_performance(branch_id: int, days=30) -> list:
    start_dt = datetime.utcnow() - timedelta(days=days)
    query = db.session.query(
        Category.category_id,
        Category.name.label('category_name'),
        func.sum(OrderItem.quantity).label('qty_sold'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price_cents), 0).label('revenue')
    ).join(MenuItem, Category.category_id == MenuItem.category_id)\
     .join(OrderItem, MenuItem.item_id == OrderItem.item_id)\
     .join(Order, OrderItem.order_id == Order.order_id)\
     .filter(
        Order.branch_id == branch_id,
        Order.status == 'paid',
        Order.opened_at >= start_dt
     ).group_by(Category.category_id, Category.name).all()
     
    return [{
        "category_id": q.category_id,
        "category_name": q.category_name,
        "qty_sold": q.qty_sold,
        "revenue_cents": int(q.revenue or 0)
    } for q in query]

def dashboard_bundle(branch_id: int) -> dict:
    from flask import current_app
    is_testing = current_app.config.get('TESTING', False) if current_app else False
    
    if not is_testing:
        cache_key = f"dashboard_{branch_id}"
        now = datetime.utcnow()
        if cache_key in _dashboard_cache:
            cached, cached_at = _dashboard_cache[cache_key]
            if (now - cached_at).seconds < 60:
                return cached
                
    result = _build_dashboard(branch_id)
    
    if not is_testing:
        _dashboard_cache[cache_key] = (result, datetime.utcnow())
        
    return result

def _build_dashboard(branch_id: int) -> dict:
    open_orders = Order.query.filter_by(branch_id=branch_id, status='open').count()
    kitchen_orders = Order.query.filter_by(branch_id=branch_id, status='open').join(
        OrderItem, Order.order_id == OrderItem.order_id
    ).filter(OrderItem.status == 'kitchen').distinct().count()
    # Fix: call low_stock_report once, reuse result
    low_stock = low_stock_report(branch_id)
    return {
        "summary": daily_summary(branch_id),
        "revenue_trend": revenue_by_period(branch_id),
        "payment_breakdown": payment_breakdown(branch_id),
        "low_stock_alerts": low_stock,
        "open_orders": open_orders,
        "kitchen_orders": kitchen_orders,
        "low_stock_count": len(low_stock),
        "customer_snapshot": customer_snapshot(branch_id),
        "revenue_comparison": revenue_comparison(branch_id),
    }


def customer_snapshot(branch_id: int) -> dict:
    """Returns a lightweight loyalty customer overview for the dashboard."""
    from app.models import Customer, LoyaltyTransaction
    total_customers = Customer.query.count()
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = Customer.query.filter(
        Customer.created_at >= start_of_month
    ).count()
    points_outstanding = db.session.query(
        func.coalesce(func.sum(Customer.points_balance), 0)
    ).scalar() or 0
    return {
        "total_customers": total_customers,
        "new_this_month": new_this_month,
        "points_outstanding": int(points_outstanding),
    }


def revenue_comparison(branch_id: int) -> dict:
    """Compares today vs yesterday and this week vs last week revenue."""
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=today_start.weekday())
    last_week_start = week_start - timedelta(days=7)

    def _revenue(start, end):
        return int(db.session.query(
            func.coalesce(func.sum(Payment.amount_cents), 0)
        ).join(Order, Payment.order_id == Order.order_id)
        .filter(
            Order.branch_id == branch_id,
            Order.status == 'paid',
            Order.opened_at >= start,
            Order.opened_at < end,
            Payment.is_voided == 0
        ).scalar() or 0)

    today_rev = _revenue(today_start, today_start + timedelta(days=1))
    yesterday_rev = _revenue(yesterday_start, today_start)
    week_rev = _revenue(week_start, week_start + timedelta(days=7))
    last_week_rev = _revenue(last_week_start, week_start)

    def _pct(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    return {
        "today_cents": today_rev,
        "yesterday_cents": yesterday_rev,
        "today_pct_change": _pct(today_rev, yesterday_rev),
        "week_cents": week_rev,
        "last_week_cents": last_week_rev,
        "week_pct_change": _pct(week_rev, last_week_rev),
    }
