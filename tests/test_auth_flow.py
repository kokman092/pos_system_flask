import pytest
from app.models import Employee, Branch
from extensions import db, bcrypt

def test_auth_flow(app_context):
    app, client = app_context
    
    # 1. Setup Admin User
    with app.app_context():
        b = Branch(name="Test Branch", is_active=1)
        db.session.add(b)
        db.session.commit()
        
        pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
        admin = Employee(
            branch_id=b.branch_id, full_name="Admin",
            email="admin@pos.com", password_hash=pw_hash,
            role="admin", is_active=1, email_verified=1
        )
        db.session.add(admin)
        db.session.commit()
        
    # 2. Login invalid
    rv = client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'wrongpass'})
    assert rv.status_code == 200 # Renders template with flash error
    assert b'Invalid credentials' in rv.data
    
    # 3. Login valid
    rv = client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    assert rv.status_code == 302
    assert '/dashboard' in rv.location
    
    # 4. Access protected route
    rv = client.get('/dashboard')
    assert rv.status_code == 200
    assert b'Dashboard' in rv.data
    
    # 5. Logout
    rv = client.get('/auth/logout')
    assert rv.status_code == 302
    assert '/auth/login' in rv.location
