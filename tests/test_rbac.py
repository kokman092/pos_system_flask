import pytest
from app.models import Branch, Employee, Role, Permission
from extensions import db, bcrypt

@pytest.fixture(autouse=True)
def setup_rbac_test_data(app_context):
    app, client = app_context
    with app.app_context():
        # Clean data to avoid conflicts
        db.session.query(Employee).delete()
        db.session.query(Branch).delete()
        db.session.commit()
        
        # 1. Create Branch
        b = Branch(name="RBAC Test Branch", is_active=1)
        db.session.add(b)
        db.session.commit()
        
        # 2. Create Employees with the roles
        pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
        
        admin = Employee(
            branch_id=b.branch_id, full_name="Admin User",
            email="admin@pos.com", password_hash=pw_hash,
            role="admin", is_active=1, email_verified=1
        )
        manager = Employee(
            branch_id=b.branch_id, full_name="Manager User",
            email="manager@pos.com", password_hash=pw_hash,
            role="manager", is_active=1, email_verified=1
        )
        cashier = Employee(
            branch_id=b.branch_id, full_name="Cashier User",
            email="cashier@pos.com", password_hash=pw_hash,
            role="cashier", is_active=1, email_verified=1
        )
        purchaser = Employee(
            branch_id=b.branch_id, full_name="Purchaser User",
            email="purchaser@pos.com", password_hash=pw_hash,
            role="purchaser", is_active=1, email_verified=1
        )
        kitchen = Employee(
            branch_id=b.branch_id, full_name="Kitchen User",
            email="kitchen@pos.com", password_hash=pw_hash,
            role="kitchen", is_active=1, email_verified=1
        )
        db.session.add_all([admin, manager, cashier, purchaser, kitchen])
        db.session.commit()
        
    yield


def test_cashier_access_limits(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'cashier@pos.com', 'password': 'password123'})
    
    # Can access POS
    rv = client.get('/pos')
    assert rv.status_code == 200
    
    # Cannot access Dashboard
    rv = client.get('/dashboard')
    assert rv.status_code == 403
    
    # Cannot access Inventory
    rv = client.get('/inventory')
    assert rv.status_code == 403
    
    # Cannot access Reports
    rv = client.get('/reports')
    assert rv.status_code == 403
    
    # Cannot access Roles
    rv = client.get('/admin/roles')
    assert rv.status_code == 403
    
    # Cannot access Settings
    rv = client.get('/settings')
    assert rv.status_code == 403


def test_purchaser_access_limits(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'purchaser@pos.com', 'password': 'password123'})
    
    # Cannot access POS
    rv = client.get('/pos')
    assert rv.status_code == 403
    
    # Cannot access Dashboard
    rv = client.get('/dashboard')
    assert rv.status_code == 403
    
    # Can access Inventory
    rv = client.get('/inventory')
    assert rv.status_code == 200
    
    # Cannot access Reports
    rv = client.get('/reports')
    assert rv.status_code == 403
    
    # Cannot access Roles
    rv = client.get('/admin/roles')
    assert rv.status_code == 403
    
    # Cannot access Settings
    rv = client.get('/settings')
    assert rv.status_code == 403


def test_manager_access_limits(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'manager@pos.com', 'password': 'password123'})
    
    # Can access POS
    rv = client.get('/pos')
    assert rv.status_code == 200
    
    # Can access Dashboard
    rv = client.get('/dashboard')
    assert rv.status_code == 200
    
    # Can access Inventory
    rv = client.get('/inventory')
    assert rv.status_code == 200
    
    # Can access Reports
    rv = client.get('/reports')
    assert rv.status_code == 200
    
    # Cannot access Roles
    rv = client.get('/admin/roles')
    assert rv.status_code == 403
    
    # Cannot access Settings
    rv = client.get('/settings')
    assert rv.status_code == 403


def test_admin_access_limits(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    # Can access everything
    assert client.get('/pos').status_code == 200
    assert client.get('/dashboard').status_code == 200
    assert client.get('/inventory').status_code == 200
    assert client.get('/reports').status_code == 200
    assert client.get('/admin/roles').status_code == 200
    assert client.get('/settings').status_code == 200
