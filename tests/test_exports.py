import io
import csv
import pytest
from datetime import datetime, timedelta
from app.models import Order, Payment, MenuItem, Category, Ingredient, Branch, Employee, WasteLog
from extensions import db, bcrypt

@pytest.fixture(autouse=True)
def setup_export_test_data(app_context):
    app, client = app_context
    with app.app_context():
        # Clean data to avoid conflicts
        db.session.query(WasteLog).delete()
        db.session.query(Payment).delete()
        db.session.query(Order).delete()
        db.session.query(Employee).delete()
        db.session.query(Ingredient).delete()
        db.session.query(MenuItem).delete()
        db.session.query(Category).delete()
        db.session.query(Branch).delete()
        db.session.commit()
        
        # 1. Create Branches
        b1 = Branch(name="Test Branch 1", is_active=1)
        b2 = Branch(name="Test Branch 2", is_active=1)
        db.session.add_all([b1, b2])
        db.session.commit()
        
        # 2. Create Employees
        pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
        admin = Employee(
            branch_id=b1.branch_id, full_name="Admin User",
            email="admin@pos.com", password_hash=pw_hash,
            role="admin", is_active=1, email_verified=1
        )
        manager = Employee(
            branch_id=b1.branch_id, full_name="Manager User",
            email="manager@pos.com", password_hash=pw_hash,
            role="manager", is_active=1, email_verified=1
        )
        db.session.add_all([admin, manager])
        db.session.commit()
        
        # 3. Create Menu Items & Categories
        cat = Category(name="Mains")
        db.session.add(cat)
        db.session.commit()
        
        item = MenuItem(name="Burger", category_id=cat.category_id, branch_id=b1.branch_id, price_cents=1000, is_active=1)
        db.session.add(item)
        db.session.commit()
        
        # 4. Create Ingredients
        ing = Ingredient(name="Beef Patty", unit="pcs", qty_in_stock=100.0, cost_per_unit_cents=150, reorder_level=10.0, branch_id=b1.branch_id)
        db.session.add(ing)
        db.session.commit()
        
        # 5. Create Order & Payment
        order = Order(branch_id=b1.branch_id, status="paid", opened_at=datetime.utcnow())
        db.session.add(order)
        db.session.commit()
        
        payment = Payment(order_id=order.order_id, amount_cents=1000, method="cash", is_voided=0, paid_at=datetime.utcnow())
        db.session.add(payment)
        db.session.commit()
        
        # 6. Create Waste Log
        waste = WasteLog(branch_id=b1.branch_id, ingredient_id=ing.ingredient_id, qty=2.0, unit_cost_cents=150, reason="Expired", created_at=datetime.utcnow())
        db.session.add(waste)
        db.session.commit()
        
    yield


def test_export_endpoints_authentication(app_context):
    app, client = app_context
    client.get('/auth/logout')
    rv = client.get('/reports/export/revenue.csv')
    assert rv.status_code in [302, 401]


def test_export_revenue_csv(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    rv = client.get(f'/reports/export/revenue.csv?start_date={today}&end_date={today}')
    assert rv.status_code == 200
    assert 'text/csv' in rv.content_type
    assert 'attachment; filename=revenue_report_' in rv.headers.get('Content-Disposition', '')
    
    data = rv.data.decode('utf-8-sig')
    reader = csv.reader(io.StringIO(data))
    headers = next(reader)
    assert headers == ["date", "order_count", "revenue_cents", "revenue_display"]


def test_export_revenue_xlsx(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    rv = client.get(f'/reports/export/revenue.xlsx?start_date={today}&end_date={today}')
    assert rv.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in rv.content_type
    assert 'attachment; filename=revenue_report_' in rv.headers.get('Content-Disposition', '')


def test_export_payments_csv(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    rv = client.get(f'/reports/export/payments.csv?start_date={today}&end_date={today}')
    assert rv.status_code == 200
    assert 'text/csv' in rv.content_type
    
    data = rv.data.decode('utf-8-sig')
    reader = csv.reader(io.StringIO(data))
    headers = next(reader)
    assert headers == ["payment_method", "transaction_count", "total_cents", "total_display"]


def test_export_daily_pdf(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    rv = client.get(f'/reports/export/daily.pdf?date={today}')
    assert rv.status_code == 200
    assert 'application/pdf' in rv.content_type
    assert 'attachment; filename=daily_report_' in rv.headers.get('Content-Disposition', '')


def test_export_shift_pdf(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    today = datetime.utcnow().strftime('%Y-%m-%d')
    rv = client.get(f'/reports/export/shift.pdf?date={today}&shift=morning')
    assert rv.status_code == 200
    assert 'application/pdf' in rv.content_type
    assert 'attachment; filename=shift_report_' in rv.headers.get('Content-Disposition', '')


def test_export_date_validation_limit(app_context):
    app, client = app_context
    # Log in as a manager to test 90 days limit guard
    client.post('/auth/login', data={'email': 'manager@pos.com', 'password': 'password123'})
    
    # 100 days range should fail for manager role
    rv = client.get('/reports/export/revenue.csv?start_date=2026-01-01&end_date=2026-04-20')
    assert rv.status_code == 400
    assert b'Ad-hoc export range exceeds' in rv.data
    
    # Log in as admin
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    # Admin is allowed to bypass the 90 days range limit
    rv = client.get('/reports/export/revenue.csv?start_date=2026-01-01&end_date=2026-04-20')
    assert rv.status_code == 200
