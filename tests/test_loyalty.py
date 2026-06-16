import pytest
from app.models import Customer, LoyaltyTransaction, Branch, Employee, Order
from extensions import db, bcrypt
from datetime import datetime

@pytest.fixture(autouse=True)
def setup_loyalty_test_data(app_context):
    app, client = app_context
    with app.app_context():
        db.session.query(LoyaltyTransaction).delete()
        db.session.query(Order).delete()
        db.session.query(Customer).delete()
        db.session.query(Employee).delete()
        db.session.query(Branch).delete()
        db.session.commit()
        
        b = Branch(name="Loyalty Branch", is_active=1)
        db.session.add(b)
        db.session.commit()
        
        pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
        cashier = Employee(
            branch_id=b.branch_id, full_name="Cashier User",
            email="cashier@pos.com", password_hash=pw_hash,
            role="cashier", is_active=1, email_verified=1
        )
        db.session.add(cashier)
        
        c1 = Customer(name="George Harrison", phone="+15555551234", email="george@beatles.com", points_balance=500, total_spent_cents=10000)
        c2 = Customer(name="John Lennon", phone="+15555559999", email="john@beatles.com", points_balance=100, total_spent_cents=2000)
        db.session.add_all([c1, c2])
        db.session.commit()
        
    yield


def test_loyalty_page_requires_login(app_context):
    app, client = app_context
    client.get('/auth/logout')
    rv = client.get('/loyalty')
    assert rv.status_code == 302
    assert '/auth/login' in rv.location


def test_loyalty_page_loads_and_searches(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'cashier@pos.com', 'password': 'password123'})
    
    # 1. Main page empty state
    rv = client.get('/loyalty')
    assert rv.status_code == 200
    assert b'Search for a customer to view their loyalty profile' in rv.data
    
    # 2. Search by phone
    rv = client.get('/loyalty?search=%2B15555551234&search_type=phone')
    assert rv.status_code == 200
    assert b'George Harrison' in rv.data
    assert b'500 pts' in rv.data
    assert b'Bronze' in rv.data


def test_api_loyalty_search(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'cashier@pos.com', 'password': 'password123'})
    
    rv = client.get('/api/loyalty/search?q=george&type=name')
    assert rv.status_code == 200
    json_data = rv.get_json()
    assert json_data['status'] == 'success'
    assert 'customers' in json_data['data']
    customers = json_data['data']['customers']
    assert len(customers) == 1
    assert customers[0]['name'] == 'George Harrison'
    assert customers[0]['phone'] == '+15555551234'


def test_api_loyalty_get_customer_summary(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'cashier@pos.com', 'password': 'password123'})
    
    with app.app_context():
        customer = Customer.query.filter_by(name="George Harrison").first()
        customer_id = customer.customer_id
        
    rv = client.get(f'/api/loyalty/{customer_id}')
    assert rv.status_code == 200
    json_data = rv.get_json()
    assert json_data['status'] == 'success'
    assert json_data['data']['name'] == 'George Harrison'
    assert json_data['data']['points_balance'] == 500
    assert json_data['data']['tier']['name'] == 'Bronze'


def test_api_loyalty_create_customer(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'cashier@pos.com', 'password': 'password123'})
    
    rv = client.post('/api/loyalty/customer', data={
        'name': 'Ringo Starr',
        'phone': '+15555557777',
        'email': 'ringo@beatles.com'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        customer = Customer.query.filter_by(name="Ringo Starr").first()
        assert customer is not None
        assert customer.phone == '+15555557777'
        assert customer.points_balance == 0


def test_api_loyalty_redeem_and_attach(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'cashier@pos.com', 'password': 'password123'})
    
    with app.app_context():
        b = Branch.query.first()
        customer = Customer.query.filter_by(name="George Harrison").first()
        customer_id = customer.customer_id
        
        # Create an open order
        order = Order(branch_id=b.branch_id, status="open")
        db.session.add(order)
        db.session.commit()
        order_id = order.order_id
        
    # 1. Attempt to redeem more points than balance (should fail)
    rv = client.post('/api/loyalty/redeem', json={
        'customer_id': customer_id,
        'order_id': order_id,
        'points_to_redeem': 1000
    })
    assert rv.status_code == 400
    
    # 2. Attach customer to order (points = 0)
    rv = client.post('/api/loyalty/redeem', json={
        'customer_id': customer_id,
        'order_id': order_id,
        'points_to_redeem': 0
    })
    assert rv.status_code == 200
    with app.app_context():
        o = db.session.get(Order, order_id)
        assert o.customer_id == customer_id
        assert o.discount_cents == 0
        
    # 3. Redeem points successfully
    rv = client.post('/api/loyalty/redeem', json={
        'customer_id': customer_id,
        'order_id': order_id,
        'points_to_redeem': 300
    })
    assert rv.status_code == 200
    json_data = rv.get_json()
    assert json_data['data']['discount_cents'] == 1500  # 300 points // 100 * 500 = 1500 cents
    assert json_data['data']['new_balance'] == 200
    
    with app.app_context():
        o = db.session.get(Order, order_id)
        assert o.customer_id == customer_id
        assert o.discount_cents == 1500
        c = db.session.get(Customer, customer_id)
        assert c.points_balance == 200


def test_api_loyalty_search_all(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'cashier@pos.com', 'password': 'password123'})
    
    rv = client.get('/api/loyalty/search?all=true')
    assert rv.status_code == 200
    json_data = rv.get_json()
    assert json_data['status'] == 'success'
    assert 'customers' in json_data['data']
    customers = json_data['data']['customers']
    assert len(customers) == 2  # both John and George

