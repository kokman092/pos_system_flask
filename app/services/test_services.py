"""Test Services"""
import pytest
from datetime import datetime, timedelta
from flask import Flask
from extensions import db, bcrypt
from app.models import Branch, Employee, UserSession, EmailVerification, Order, OrderItem, RestaurantTable, MenuItem, Ingredient, StockBatch, ItemIngredient, Customer, LoyaltyTransaction
from app.services.auth_service import login, reset_password
from app.services.order_service import add_item, send_to_kitchen, process_payment
from app.services.loyalty_service import award_points
from app.services.inventory_service import deduct_for_items

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def test_db(app):
    # Setup test data
    branch = Branch(name="Test Branch")
    db.session.add(branch)
    db.session.flush()

    pw_hash = bcrypt.generate_password_hash("Password123!").decode('utf-8')
    emp = Employee(branch_id=branch.branch_id, full_name="Test Emp", role="admin", email="test@test.com", password_hash=pw_hash, email_verified=1, is_active=1)
    db.session.add(emp)
    
    table = RestaurantTable(branch_id=branch.branch_id, table_number="T1", status="occupied")
    db.session.add(table)
    db.session.flush()
    
    order = Order(branch_id=branch.branch_id, table_id=table.table_id, employee_id=emp.employee_id, order_type="dine_in", status="open", pax=2)
    db.session.add(order)
    
    menu_item = MenuItem(name="Burger", price_cents=1000, is_available=1)
    db.session.add(menu_item)
    db.session.flush()

    ing = Ingredient(name="Beef", unit="g", qty_in_stock=1000, branch_id=branch.branch_id)
    db.session.add(ing)
    db.session.flush()

    batch1 = StockBatch(ingredient_id=ing.ingredient_id, qty_received=500, qty_remaining=500, cost_per_unit_cents=1, received_at=datetime.utcnow() - timedelta(days=2))
    batch2 = StockBatch(ingredient_id=ing.ingredient_id, qty_received=500, qty_remaining=500, cost_per_unit_cents=1, received_at=datetime.utcnow() - timedelta(days=1))
    db.session.add_all([batch1, batch2])
    
    item_ing = ItemIngredient(item_id=menu_item.item_id, ingredient_id=ing.ingredient_id, qty_used=200)
    db.session.add(item_ing)
    
    cust = Customer(name="John", phone="123", email="j@j.com", points_balance=0, total_spent_cents=0)
    db.session.add(cust)
    
    db.session.commit()
    
    return {
        'branch': branch,
        'employee': emp,
        'table': table,
        'order': order,
        'menu_item': menu_item,
        'ingredient': ing,
        'batch1': batch1,
        'batch2': batch2,
        'customer': cust
    }

def test_login_success(test_db):
    session = login("test@test.com", "Password123!", "127.0.0.1", "pytest")
    assert session is not None
    assert session.employee_id == test_db['employee'].employee_id
    assert test_db['employee'].failed_login_count == 0

def test_login_wrong_password_and_lockout(test_db):
    for i in range(4):
        with pytest.raises(ValueError, match="Invalid credentials"):
            login("test@test.com", "wrong", "127.0.0.1", "pytest")
            
    assert test_db['employee'].failed_login_count == 4
    
    # 5th fail locks out
    with pytest.raises(ValueError, match="Invalid credentials"):
        login("test@test.com", "wrong", "127.0.0.1", "pytest")
        
    assert test_db['employee'].failed_login_count == 5
    assert test_db['employee'].locked_until is not None
    assert test_db['employee'].locked_until > datetime.utcnow()
    
    # 6th attempt should raise locked
    with pytest.raises(PermissionError, match="Account is locked"):
        login("test@test.com", "wrong", "127.0.0.1", "pytest")

def test_add_item_price_snapshot(test_db):
    order_id = test_db['order'].order_id
    item_id = test_db['menu_item'].item_id
    
    # Add item
    oi = add_item(order_id, item_id, quantity=2, notes="Extra cheese", seat_number=1, modifiers=[])
    assert oi.unit_price_cents == 1000
    assert oi.status == 'pending'
    
    # Change original price
    mi = db.session.get(MenuItem, item_id)
    mi.price_cents = 1500
    db.session.commit()
    
    # Snapshot should remain
    oi_check = db.session.get(OrderItem, oi.order_item_id)
    assert oi_check.unit_price_cents == 1000

def test_send_to_kitchen_inventory_deducted(test_db):
    order_id = test_db['order'].order_id
    item_id = test_db['menu_item'].item_id
    oi = add_item(order_id, item_id, quantity=2, notes="", seat_number=1, modifiers=[])
    
    # 2 items * 200g = 400g deducted
    items = send_to_kitchen(order_id, [oi.order_item_id])
    assert len(items) == 1
    assert items[0].status == 'kitchen'
    
    ing = db.session.get(Ingredient, test_db['ingredient'].ingredient_id)
    assert ing.qty_in_stock == 600

def test_deduct_for_items_fifo(test_db):
    order_id = test_db['order'].order_id
    item_id = test_db['menu_item'].item_id
    # We want to deduct 600g (3 quantity * 200g)
    oi = add_item(order_id, item_id, quantity=3, notes="", seat_number=1, modifiers=[])
    
    deduct_for_items([oi])
    
    ing = db.session.get(Ingredient, test_db['ingredient'].ingredient_id)
    assert ing.qty_in_stock == 400
    
    batch1 = db.session.get(StockBatch, test_db['batch1'].batch_id)
    batch2 = db.session.get(StockBatch, test_db['batch2'].batch_id)
    
    # batch1 had 500, batch2 had 500
    # 600 deducted -> batch1 should be 0, batch2 should be 400
    assert batch1.qty_remaining == 0
    assert batch2.qty_remaining == 400

def test_process_payment(test_db):
    order = test_db['order']
    oi = add_item(order.order_id, test_db['menu_item'].item_id, quantity=1, notes="", seat_number=1, modifiers=[])
    oi.status = 'served'
    
    order.status = 'served'
    db.session.commit()
    
    # Total is 1000 cents
    payment = process_payment(order.order_id, 'cash', 1000, 1500, 'REF123', test_db['employee'].employee_id)
    assert payment.amount_cents == 1000
    assert payment.change_cents == 500
    
    o_check = db.session.get(Order, order.order_id)
    assert o_check.status == 'paid'
    
    t_check = db.session.get(RestaurantTable, test_db['table'].table_id)
    assert t_check.status == 'cleaning'

def test_award_points(test_db):
    cust_id = test_db['customer'].customer_id
    order_id = test_db['order'].order_id
    
    # Award for 1500 cents -> 15 points
    tx = award_points(cust_id, order_id, 1500)
    assert tx.points_earned == 15
    
    cust = db.session.get(Customer, cust_id)
    assert cust.points_balance == 15
    assert cust.total_spent_cents == 1500

def test_reset_password_revokes_sessions(test_db):
    emp = test_db['employee']
    # Create active sessions
    s1 = UserSession(employee_id=emp.employee_id, session_token="s1", expires_at=datetime.utcnow() + timedelta(hours=1))
    s2 = UserSession(employee_id=emp.employee_id, session_token="s2", expires_at=datetime.utcnow() + timedelta(hours=1))
    db.session.add_all([s1, s2])
    
    # Create valid reset token
    ev = EmailVerification(employee_id=emp.employee_id, token="reset123", token_type="reset_password", expires_at=datetime.utcnow() + timedelta(hours=1))
    db.session.add(ev)
    db.session.commit()
    
    reset_password("reset123", "NewPass1!")
    
    s1_check = UserSession.query.filter_by(session_token="s1").first()
    s2_check = UserSession.query.filter_by(session_token="s2").first()
    
    assert s1_check.is_revoked == 1
    assert s2_check.is_revoked == 1
    
    # Verify new password
    emp_check = db.session.get(Employee, emp.employee_id)
    assert bcrypt.check_password_hash(emp_check.password_hash, "NewPass1!")
