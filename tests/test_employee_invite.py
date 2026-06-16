import pytest
from app.models import Employee, Branch
from app.services import auth_service
from extensions import db, bcrypt

@pytest.fixture(autouse=True)
def setup_employee_test_data(app_context):
    app, client = app_context
    with app.app_context():
        db.session.query(Employee).delete()
        db.session.query(Branch).delete()
        db.session.commit()
        
        b = Branch(name="Test Branch", is_active=1)
        db.session.add(b)
        db.session.commit()
        
        pw_hash = bcrypt.generate_password_hash("StrongPass1!").decode('utf-8')
        admin = Employee(
            branch_id=b.branch_id, full_name="Admin User",
            email="admin@pos.com", password_hash=pw_hash,
            role="admin", is_active=1, email_verified=1
        )
        db.session.add(admin)
        db.session.commit()
    yield


def test_register_employee_by_admin_succeeds_and_can_login(app_context):
    app, client = app_context
    
    with app.app_context():
        b = Branch.query.first()
        branch_id = b.branch_id
        
    # Register via service
    with app.app_context():
        emp = auth_service.register_employee(
            branch_id=branch_id,
            full_name="New Waiter",
            role="waiter",
            email="waiter_new@pos.com",
            password="StrongPass2!",
            created_by_admin=True
        )
        assert emp.email_verified == 1
        assert emp.is_active == 1
        
    # Login immediately
    rv = client.post('/auth/login', data={'email': 'waiter_new@pos.com', 'password': 'StrongPass2!'})
    assert rv.status_code == 302
    assert '/dashboard' in rv.location


def test_invite_form_validations(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'StrongPass1!'})
    
    with app.app_context():
        b = Branch.query.first()
        branch_id = b.branch_id
    
    # 1. Duplicate email should fail
    rv = client.post('/admin/employees/invite', data={
        'full_name': 'Another Admin',
        'email': 'admin@pos.com',
        'password': 'StrongPass3!',
        'confirm_password': 'StrongPass3!',
        'role': 'admin',
        'branch_id': branch_id
    })
    assert rv.status_code == 302
    # Check flash messages by GETing index page
    rv_get = client.get('/admin/employees')
    assert b'Email already registered' in rv_get.data

    # 2. Weak password should fail
    rv = client.post('/admin/employees/invite', data={
        'full_name': 'Another Waiter',
        'email': 'waiter_weak@pos.com',
        'password': 'weak',
        'confirm_password': 'weak',
        'role': 'waiter',
        'branch_id': branch_id
    })
    assert rv.status_code == 302
    rv_get = client.get('/admin/employees')
    assert b'Password must contain' in rv_get.data or b'password' in rv_get.data.lower()


def test_role_restrictions(app_context):
    app, client = app_context
    
    with app.app_context():
        b = Branch.query.first()
        branch_id = b.branch_id
        
        # Create a waiter
        pw_hash = bcrypt.generate_password_hash("StrongPass1!").decode('utf-8')
        waiter = Employee(
            branch_id=branch_id, full_name="Waiter User",
            email="waiter@pos.com", password_hash=pw_hash,
            role="waiter", is_active=1, email_verified=1
        )
        db.session.add(waiter)
        db.session.commit()

    # Log in as waiter
    client.post('/auth/login', data={'email': 'waiter@pos.com', 'password': 'StrongPass1!'})
    
    # Waiter cannot access reports (/reports)
    rv = client.get('/reports')
    assert rv.status_code == 403
    
    # Waiter cannot access settings (/settings)
    rv = client.get('/settings')
    assert rv.status_code == 403
    
    # Waiter cannot access employees (/admin/employees)
    rv = client.get('/admin/employees')
    assert rv.status_code == 403
    
    # Waiter CAN access POS (/pos)
    rv = client.get('/pos')
    assert rv.status_code == 200
