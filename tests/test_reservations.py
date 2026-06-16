import pytest
from app.models import Reservation, RestaurantTable, Branch, Employee
from extensions import db, bcrypt
from datetime import datetime, timedelta

@pytest.fixture(autouse=True)
def setup_reservations_test_data(app_context):
    app, client = app_context
    with app.app_context():
        # Clean up tables
        db.session.query(Reservation).delete()
        db.session.query(RestaurantTable).delete()
        db.session.query(Employee).delete()
        db.session.query(Branch).delete()
        db.session.commit()
        
        # 1. Create Branch
        b = Branch(name="Reservations Branch", is_active=1)
        db.session.add(b)
        db.session.commit()
        
        # 2. Create Employee
        pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
        waiter = Employee(
            branch_id=b.branch_id, full_name="Waiter User",
            email="waiter@pos.com", password_hash=pw_hash,
            role="waiter", is_active=1, email_verified=1
        )
        db.session.add(waiter)
        db.session.commit()
        
        # 3. Create Tables
        t1 = RestaurantTable(table_number="10", capacity=4, status="available", branch_id=b.branch_id)
        t2 = RestaurantTable(table_number="11", capacity=2, status="available", branch_id=b.branch_id)
        db.session.add_all([t1, t2])
        db.session.commit()
        
    yield


def test_reservations_page_requires_login(app_context):
    app, client = app_context
    client.get('/auth/logout')
    rv = client.get('/reservations')
    assert rv.status_code == 302
    assert '/auth/login' in rv.location


def test_reservations_page_loads_for_waiter(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'waiter@pos.com', 'password': 'password123'})
    rv = client.get('/reservations')
    assert rv.status_code == 200
    assert b'Reservations' in rv.data
    assert b'Active Reservations' in rv.data


def test_create_reservation(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'waiter@pos.com', 'password': 'password123'})
    
    with app.app_context():
        table = RestaurantTable.query.filter_by(table_number="10").first()
        table_id = table.table_id
        
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    
    rv = client.post('/reservations', data={
        'customer_name': 'Jane Doe',
        'customer_email': 'jane@example.com',
        'customer_phone': '+1234567890',
        'party_size': 3,
        'table_id': table_id,
        'reserved_at': tomorrow_str,
        'notes': 'Gluten free guests'
    })
    
    assert rv.status_code == 302
    
    with app.app_context():
        res = Reservation.query.filter_by(customer_name='Jane Doe').first()
        assert res is not None
        assert res.party_size == 3
        assert res.customer_phone == '+1234567890'
        assert res.table_id == table_id
        assert res.status == 'pending'


def test_update_reservation_status(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'waiter@pos.com', 'password': 'password123'})
    
    with app.app_context():
        b = Branch.query.first()
        table = RestaurantTable.query.filter_by(table_number="10").first()
        table_id = table.table_id
        
        # Create pending reservation
        res = Reservation(
            branch_id=b.branch_id,
            customer_name="John Smith",
            party_size=2,
            reserved_at=datetime.utcnow() + timedelta(hours=2),
            table_id=table_id,
            status="pending"
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.reservation_id
        
    # 1. Update status to confirmed
    rv = client.post(f'/reservations/{res_id}/status', data={
        'status': 'confirmed'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        res = db.session.get(Reservation, res_id)
        assert res.status == 'confirmed'
        
    # 2. Update status to seated and verify table becomes occupied
    rv = client.post(f'/reservations/{res_id}/status', data={
        'status': 'seated'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        res = db.session.get(Reservation, res_id)
        assert res.status == 'seated'
        table = db.session.get(RestaurantTable, table_id)
        assert table.status == 'occupied'


def test_delete_reservation(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'waiter@pos.com', 'password': 'password123'})
    
    with app.app_context():
        b = Branch.query.first()
        res = Reservation(
            branch_id=b.branch_id,
            customer_name="Alice Brown",
            party_size=4,
            reserved_at=datetime.utcnow() + timedelta(hours=5),
            status="pending"
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.reservation_id
        
    # Delete (cancels) reservation
    rv = client.delete(f'/reservations/{res_id}')
    assert rv.status_code == 200
    
    with app.app_context():
        res = db.session.get(Reservation, res_id)
        assert res.status == 'cancelled'


def test_duplicate_reservation_fails(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'waiter@pos.com', 'password': 'password123'})
    
    with app.app_context():
        table = RestaurantTable.query.filter_by(table_number="10").first()
        table_id = table.table_id
        
    reserved_time = (datetime.now() + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    reserved_time_str = reserved_time.strftime('%Y-%m-%dT%H:%M')
    
    # First reservation
    rv1 = client.post('/reservations', data={
        'customer_name': 'George Harrison',
        'customer_email': 'george@beatles.com',
        'customer_phone': '+1111111111',
        'party_size': 2,
        'table_id': table_id,
        'reserved_at': reserved_time_str,
        'notes': ''
    })
    assert rv1.status_code == 302
    
    # Attempt duplicate reservation for the same table, time, and branch
    rv2 = client.post('/reservations', data={
        'customer_name': 'Another Guest',
        'customer_email': 'another@example.com',
        'customer_phone': '+2222222222',
        'party_size': 2,
        'table_id': table_id,
        'reserved_at': reserved_time_str,
        'notes': ''
    })
    # Should redirect back
    assert rv2.status_code == 302
    
    # Verify warning message appears in the flashed messages
    rv_get = client.get('/reservations')
    assert b'A reservation already exists for this table at the selected time.' in rv_get.data


def test_duplicate_reservation_with_cancelled_allowed(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'waiter@pos.com', 'password': 'password123'})
    
    with app.app_context():
        table = RestaurantTable.query.filter_by(table_number="10").first()
        table_id = table.table_id
        
    reserved_time = (datetime.now() + timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    reserved_time_str = reserved_time.strftime('%Y-%m-%dT%H:%M')
    
    # First reservation
    rv1 = client.post('/reservations', data={
        'customer_name': 'Paul McCartney',
        'customer_email': 'paul@beatles.com',
        'customer_phone': '+3333333333',
        'party_size': 2,
        'table_id': table_id,
        'reserved_at': reserved_time_str,
        'notes': ''
    })
    assert rv1.status_code == 302
    
    with app.app_context():
        res1 = Reservation.query.filter_by(customer_name='Paul McCartney').first()
        res1_id = res1.reservation_id
        
    # Cancel first reservation
    rv_cancel = client.delete(f'/reservations/{res1_id}')
    assert rv_cancel.status_code == 200
    
    # Attempt second reservation at the same time and table (should succeed since the first was cancelled)
    rv2 = client.post('/reservations', data={
        'customer_name': 'John Lennon',
        'customer_email': 'john@beatles.com',
        'customer_phone': '+4444444444',
        'party_size': 2,
        'table_id': table_id,
        'reserved_at': reserved_time_str,
        'notes': ''
    })
    assert rv2.status_code == 302
    
    with app.app_context():
        res2 = Reservation.query.filter_by(customer_name='John Lennon').first()
        assert res2 is not None
        assert res2.status == 'pending'
