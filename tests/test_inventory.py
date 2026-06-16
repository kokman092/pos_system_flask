import pytest
from app.models import Ingredient, InventoryCountSession, InventoryCountItem, Branch, Employee, WasteLog, StockBatch
from extensions import db, bcrypt

@pytest.fixture(autouse=True)
def setup_inventory_test_data(app_context):
    app, client = app_context
    with app.app_context():
        # Clean data to avoid conflicts
        db.session.query(InventoryCountItem).delete()
        db.session.query(InventoryCountSession).delete()
        db.session.query(WasteLog).delete()
        db.session.query(StockBatch).delete()
        db.session.query(Ingredient).delete()
        db.session.query(Employee).delete()
        db.session.query(Branch).delete()
        db.session.commit()
        
        # 1. Create Branch
        b = Branch(name="Inventory Branch", is_active=1)
        db.session.add(b)
        db.session.commit()
        
        # 2. Create Admin and Manager Employee
        pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
        admin = Employee(
            branch_id=b.branch_id, full_name="Admin User",
            email="admin@pos.com", password_hash=pw_hash,
            role="admin", is_active=1, email_verified=1
        )
        db.session.add(admin)
        db.session.commit()
        
        # 3. Create Ingredients
        ing1 = Ingredient(name="Beef Patty", unit="pcs", qty_in_stock=10.0, cost_per_unit_cents=150, reorder_level=5.0, branch_id=b.branch_id)
        ing2 = Ingredient(name="Lettuce", unit="kg", qty_in_stock=2.0, cost_per_unit_cents=50, reorder_level=3.0, branch_id=b.branch_id)
        db.session.add_all([ing1, ing2])
        db.session.commit()
        
    yield


def test_inventory_page_requires_login(app_context):
    app, client = app_context
    client.get('/auth/logout') # Ensure logged out
    rv = client.get('/inventory')
    assert rv.status_code == 302
    assert '/auth/login' in rv.location


def test_inventory_page_loads_for_admin(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    rv = client.get('/inventory')
    assert rv.status_code == 200
    assert b'Stock Levels' in rv.data
    assert b'Beef Patty' in rv.data
    assert b'Lettuce' in rv.data


def test_add_batch_route(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    with app.app_context():
        ing = Ingredient.query.filter_by(name="Beef Patty").first()
        ing_id = ing.ingredient_id
        initial_qty = ing.qty_in_stock
        

        
    rv = client.post('/inventory/batch', data={
        'ingredient_id': ing_id,
        'qty_received': '5.500',
        'cost_per_unit': '1.50',
        'supplier_ref': 'SUP-001'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        ing = db.session.get(Ingredient, ing_id)
        assert float(ing.qty_in_stock) == float(initial_qty) + 5.500



def test_adjust_stock_route(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    with app.app_context():
        ing = Ingredient.query.filter_by(name="Beef Patty").first()
        ing_id = ing.ingredient_id
        
    rv = client.post('/inventory/adjust', data={
        'ingredient_id': ing_id,
        'new_qty': '15.000',
        'reason': 'Inventory adjustment check'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        ing = db.session.get(Ingredient, ing_id)
        assert float(ing.qty_in_stock) == 15.000


def test_log_waste_route(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    with app.app_context():
        ing = Ingredient.query.filter_by(name="Beef Patty").first()
        ing_id = ing.ingredient_id
        
        # Need to seed a stock batch because waste logs deduct using FIFO from StockBatch
        b = Branch.query.first()
        batch = StockBatch(
            ingredient_id=ing_id,
            qty_received=10.0,
            qty_remaining=10.0,
            cost_per_unit_cents=150
        )
        db.session.add(batch)
        db.session.commit()
        
        initial_qty = ing.qty_in_stock
        
    rv = client.post('/inventory/waste', data={
        'ingredient_id': ing_id,
        'qty': '2.500',
        'reason': 'Expired item'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        ing = db.session.get(Ingredient, ing_id)
        assert float(ing.qty_in_stock) == float(initial_qty) - 2.500


def test_inventory_count_session_workflow(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})
    
    # 1. Start count session
    rv = client.post('/inventory/count/start', data={
        'session_name': 'Monthly Inventory Count'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        session = InventoryCountSession.query.filter_by(status='open').first()
        assert session is not None
        assert session.session_name == 'Monthly Inventory Count'
        session_id = session.session_id
        
        ing_beef = Ingredient.query.filter_by(name="Beef Patty").first()
        ing_lettuce = Ingredient.query.filter_by(name="Lettuce").first()
        beef_id = ing_beef.ingredient_id
        lettuce_id = ing_lettuce.ingredient_id
        
    # 2. Submit counts
    rv = client.post(f'/inventory/count/{session_id}/submit', data={
        f'counted_qty_{beef_id}': '12.000',
        f'counted_qty_{lettuce_id}': '1.500'
    })
    assert rv.status_code == 302
    
    with app.app_context():
        session = db.session.get(InventoryCountSession, session_id)
        assert session.status == 'completed'
        
        beef_item = InventoryCountItem.query.filter_by(session_id=session_id, ingredient_id=beef_id).first()
        assert float(beef_item.counted_qty) == 12.000
        assert float(beef_item.variance_qty) == 2.000 # 12.0 - 10.0
        
        lettuce_item = InventoryCountItem.query.filter_by(session_id=session_id, ingredient_id=lettuce_id).first()
        assert float(lettuce_item.counted_qty) == 1.500
        assert float(lettuce_item.variance_qty) == -0.500 # 1.5 - 2.0
        
    # 3. Confirm count adjustment
    rv = client.post(f'/inventory/count/{session_id}/confirm')
    assert rv.status_code == 302
    
    with app.app_context():
        ing_beef = db.session.get(Ingredient, beef_id)
        ing_lettuce = db.session.get(Ingredient, lettuce_id)
        
        assert float(ing_beef.qty_in_stock) == 12.000
        assert float(ing_lettuce.qty_in_stock) == 1.500


def test_supplier_registration_route(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    rv = client.post('/inventory/suppliers', data={
        'name': 'Test Supplier Inc',
        'contact_name': 'Alice Smith',
        'phone': '123-4567',
        'email': 'alice@testsupplier.com',
        'address': '123 Test St',
        'image_path': 'img/placeholders/menu-placeholder.jpg'
    })
    assert rv.status_code == 302

    with app.app_context():
        from app.models import Supplier
        supplier = Supplier.query.filter_by(name='Test Supplier Inc').first()
        assert supplier is not None
        assert supplier.contact_name == 'Alice Smith'
        assert supplier.image_path == 'img/placeholders/menu-placeholder.jpg'


def test_purchase_order_creation_and_receiving_flow(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    with app.app_context():
        from app.models import Supplier
        supplier = Supplier(name='Local Supplier', is_active=1)
        db.session.add(supplier)
        db.session.commit()
        supplier_id = supplier.supplier_id

        ing = Ingredient.query.filter_by(name="Beef Patty").first()
        ing_id = ing.ingredient_id
        initial_qty = float(ing.qty_in_stock)

    # 1. Create Purchase Order
    rv = client.post('/inventory/purchase-orders', data={
        'supplier_id': supplier_id,
        'expected_at': '2026-06-20',
        'notes': 'Urgent meat restock',
        'items-0-ingredient_id': ing_id,
        'items-0-ordered_qty': '10.000',
        'items-0-unit_cost': '2.00'
    })
    assert rv.status_code == 302

    with app.app_context():
        from app.models import PurchaseOrder
        po = PurchaseOrder.query.filter_by(supplier_id=supplier_id).first()
        assert po is not None
        assert po.status == 'draft'
        assert po.notes == 'Urgent meat restock'
        assert po.creator.full_name == 'Admin User'
        po_id = po.purchase_order_id
        po_item_id = po.items[0].purchase_order_item_id

    # 2. Approve Purchase Order
    rv = client.post(f'/inventory/purchase-orders/{po_id}/approve')
    assert rv.status_code == 302

    with app.app_context():
        po = db.session.get(PurchaseOrder, po_id)
        assert po.status == 'ordered'
        assert po.approver.full_name == 'Admin User'

    # 3. Receive Purchase Order (Partial receiving with batch notes)
    rv = client.post(f'/inventory/purchase-orders/{po_id}/receive', data={
        'invoice_ref': 'INV-TEST-001',
        f'received_qty_{po_item_id}': '8.000',
        f'actual_unit_cost_{po_item_id}': '2.10',
        f'notes_{po_item_id}': 'Batch Notes Test'
    })
    assert rv.status_code == 302

    with app.app_context():
        po = db.session.get(PurchaseOrder, po_id)
        assert po.status == 'partially_received'
        assert po.receiver.full_name == 'Admin User'
        assert po.invoice_ref == 'INV-TEST-001'
        
        # Verify ingredient quantity increased
        ing = db.session.get(Ingredient, ing_id)
        assert float(ing.qty_in_stock) == initial_qty + 8.000
        
        # Verify supplier price history recorded
        from app.models import SupplierPriceHistory
        history = SupplierPriceHistory.query.filter_by(supplier_id=supplier_id, ingredient_id=ing_id).first()
        assert history is not None
        assert history.unit_cost_cents == 210

        # Verify lot/batch notes are saved on StockBatch
        batch = StockBatch.query.filter_by(ingredient_id=ing_id).order_by(StockBatch.batch_id.desc()).first()
        assert batch is not None
        assert batch.notes == 'Batch Notes Test'

    # 4. Verify detail JSON API response contains auditor details and timestamps
    rv = client.get(f'/inventory/purchase-orders/{po_id}')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['purchase_order_id'] == po_id
    assert data['po_number'] is not None
    assert data['supplier_name'] == 'Local Supplier'
    assert data['status'] == 'partially_received'
    assert data['created_by_name'] == 'Admin User'
    assert data['approved_by_name'] == 'Admin User'
    assert data['received_by_name'] == 'Admin User'
    assert data['invoice_ref'] == 'INV-TEST-001'
    assert data['notes'] == 'Urgent meat restock'
    assert data['created_at'] != 'N/A'
    assert data['approved_at'] != 'N/A'
    assert data['ordered_at'] != 'N/A'
    assert data['expected_at'] == '2026-06-20'
    assert data['received_at'] != 'N/A'
    assert len(data['items']) == 1
    assert data['items'][0]['received_qty'] == 8.0
    assert data['items'][0]['unit_cost'] == 2.10


def test_supplier_performance_insights(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    from datetime import datetime, timedelta
    from decimal import Decimal
    from app.models import Supplier, PurchaseOrder, PurchaseOrderItem, Ingredient
    from app.services.inventory_service import get_supplier_performance_insights

    with app.app_context():
        # Get branch and employee
        b = db.session.query(Branch).first()
        branch_id = b.branch_id
        admin = db.session.query(Employee).filter_by(role='admin').first()
        admin_id = admin.employee_id
        
        # Get/create ingredients
        ing = Ingredient.query.filter_by(name="Beef Patty").first()
        ing_id = ing.ingredient_id
        
        # Create Suppliers
        sup = Supplier(name='Perf Supplier', is_active=1)
        db.session.add(sup)
        db.session.commit()
        sup_id = sup.supplier_id

        # 1. Create a received, on-time PO (ordered 2 days ago, expected today, received today) -> lead time 2 days
        po1 = PurchaseOrder(
            branch_id=branch_id,
            supplier_id=sup_id,
            po_number="PO-TEST-PERF-01",
            status='received',
            ordered_at=datetime.utcnow() - timedelta(days=2),
            expected_at=datetime.utcnow(),
            received_at=datetime.utcnow(),
            created_by=admin_id,
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add(po1)
        db.session.flush()
        
        poi1 = PurchaseOrderItem(
            purchase_order_id=po1.purchase_order_id,
            ingredient_id=ing_id,
            ordered_qty=Decimal('10.0'),
            received_qty=Decimal('10.0'),
            unit_cost_cents=150,
            line_total_cents=1500
        )
        db.session.add(poi1)

        # 2. Create a received, late PO (ordered 4 days ago, expected 2 days ago, received today) -> lead time 4 days
        po2 = PurchaseOrder(
            branch_id=branch_id,
            supplier_id=sup_id,
            po_number="PO-TEST-PERF-02",
            status='received',
            ordered_at=datetime.utcnow() - timedelta(days=4),
            expected_at=datetime.utcnow() - timedelta(days=2),
            received_at=datetime.utcnow(),
            created_by=admin_id,
            created_at=datetime.utcnow() - timedelta(days=4)
        )
        db.session.add(po2)
        db.session.flush()

        poi2 = PurchaseOrderItem(
            purchase_order_id=po2.purchase_order_id,
            ingredient_id=ing_id,
            ordered_qty=Decimal('5.0'),
            received_qty=Decimal('5.0'),
            unit_cost_cents=200,
            line_total_cents=1000
        )
        db.session.add(poi2)

        # 3. Create an overdue PO (expected 1 day ago, status ordered)
        po3 = PurchaseOrder(
            branch_id=branch_id,
            supplier_id=sup_id,
            po_number="PO-TEST-PERF-03",
            status='ordered',
            ordered_at=datetime.utcnow() - timedelta(days=2),
            expected_at=datetime.utcnow() - timedelta(days=1),
            created_by=admin_id,
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add(po3)
        db.session.commit()

        # Run performance calculation
        insights = get_supplier_performance_insights(branch_id)
        assert sup_id in insights
        perf = insights[sup_id]
        
        # Assertions
        # 1 on-time received, 1 late received -> 50% on-time
        assert perf['on_time_pct'] == 50.0
        
        # Lead times: PO1 has 2 days, PO2 has 4 days -> avg 3 days
        assert perf['avg_lead_time'] == 3.0
        
        # Total spend: 10 * 150 = 1500, 5 * 200 = 1000 -> 2500 cents
        assert perf['total_spend_cents'] == 2500
        
        # Overdue count: PO3 is ordered and expected 1 day ago -> 1 overdue
        assert perf['overdue_count'] == 1
        
        # Last order date should be PO3 date since it is latest created non-draft order
        assert perf['last_order_date'] == (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d')


def test_add_ingredient_route(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    with app.app_context():
        # Create a supplier to use as default
        from app.models import Supplier
        s = Supplier(name="Test default supplier")
        db.session.add(s)
        db.session.commit()
        supplier_id = s.supplier_id

    rv = client.post('/inventory/ingredients/add', data={
        'name': 'Fresh Tomatoes',
        'unit': 'kg',
        'reorder_level': '2.5',
        'default_supplier_id': supplier_id,
        'current_qty': '10.5'
    })
    assert rv.status_code == 302

    with app.app_context():
        ing = Ingredient.query.filter_by(name='Fresh Tomatoes').first()
        assert ing is not None
        assert ing.unit == 'kg'
        assert float(ing.reorder_level) == 2.5
        assert ing.default_supplier_id == supplier_id
        assert float(ing.qty_in_stock) == 10.5
        assert ing.is_active == 1

        # Check stock batch was created for initial quantity
        batch = StockBatch.query.filter_by(ingredient_id=ing.ingredient_id).first()
        assert batch is not None
        assert float(batch.qty_received) == 10.5
        assert float(batch.qty_remaining) == 10.5
        assert batch.notes == "Initial stock setup"


def test_edit_ingredient_route(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    with app.app_context():
        branch = Branch.query.first()
        ing = Ingredient(
            name="Old Ingredient",
            unit="grams",
            qty_in_stock=5.0,
            reorder_level=1.0,
            branch_id=branch.branch_id,
            is_active=1
        )
        db.session.add(ing)
        db.session.commit()
        ing_id = ing.ingredient_id

    rv = client.post(f'/inventory/ingredients/{ing_id}/edit', data={
        'name': 'Updated Ingredient Name',
        'unit': 'kg',
        'reorder_level': '3.0',
        'default_supplier_id': '0', # None
        'is_active': '0' # Inactive
    })
    assert rv.status_code == 302

    with app.app_context():
        updated_ing = db.session.get(Ingredient, ing_id)
        assert updated_ing.name == 'Updated Ingredient Name'
        assert updated_ing.unit == 'kg'
        assert float(updated_ing.reorder_level) == 3.0
        assert updated_ing.default_supplier_id is None
        assert updated_ing.is_active == 0


def test_ingredient_history_route(app_context):
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    with app.app_context():
        branch = Branch.query.first()
        ing = Ingredient(
            name="History Ingredient",
            unit="pcs",
            qty_in_stock=0.0,
            reorder_level=2.0,
            branch_id=branch.branch_id,
            is_active=1
        )
        db.session.add(ing)
        db.session.commit()
        ing_id = ing.ingredient_id

    # 1. Add Stock Batch
    rv = client.post('/inventory/batch', data={
        'ingredient_id': ing_id,
        'qty_received': '12.0',
        'cost_per_unit': '1.00',
        'supplier_ref': 'SUP-HIST-01',
        'reason': 'opening stock',
        'note': 'Setup batch'
    })
    assert rv.status_code == 302

    # 2. Log Waste (spoilage removal)
    rv = client.post('/inventory/waste', data={
        'ingredient_id': ing_id,
        'qty': '2.0',
        'reason': 'Damaged items'
    })
    assert rv.status_code == 302

    # 3. Request history JSON
    rv = client.get(f'/inventory/ingredients/{ing_id}/history')
    assert rv.status_code == 200
    res_data = rv.get_json()
    assert res_data['status'] == 'success'
    
    logs = res_data['data']
    assert len(logs) >= 2
    
    # Verify chronological sorting (descending)
    assert logs[0]['action'] == 'Stock Removed'
    assert float(logs[0]['qty_change']) == -2.0
    assert 'Damaged items' in logs[0]['reason']
    
    assert logs[1]['action'] == 'Stock Added'
    assert float(logs[1]['qty_change']) == 12.0


def test_update_supplier_route(app_context):
    """Test editing a supplier's details via POST."""
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    from app.models import Supplier
    from extensions import db

    with app.app_context():
        # Create a supplier first
        s = Supplier(name='Original Foods', contact_name='John', phone='111', email='a@b.com', is_active=1)
        db.session.add(s)
        db.session.commit()
        sid = s.supplier_id

    # Edit the supplier
    rv = client.post(f'/inventory/suppliers/{sid}/edit', data={
        'name': 'Updated Foods Co.',
        'contact_name': 'Jane',
        'phone': '222-333',
        'email': 'jane@updated.com',
        'address': '100 Main St',
        'notes': 'Delivers on Tuesdays',
        'is_preferred': '1',
        'is_active': '1'
    })
    assert rv.status_code == 302

    with app.app_context():
        sup = db.session.get(Supplier, sid)
        assert sup.name == 'Updated Foods Co.'
        assert sup.contact_name == 'Jane'
        assert sup.notes == 'Delivers on Tuesdays'
        assert sup.is_preferred == 1


def test_deactivate_supplier_route(app_context):
    """Test archiving (deactivating) a supplier."""
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    from app.models import Supplier
    from extensions import db

    with app.app_context():
        s = Supplier(name='DeactivateMe Inc.', is_active=1)
        db.session.add(s)
        db.session.commit()
        sid = s.supplier_id

    # Deactivate
    rv = client.post(f'/inventory/suppliers/{sid}/deactivate')
    assert rv.status_code == 302

    with app.app_context():
        sup = db.session.get(Supplier, sid)
        assert sup.is_active == 0

    # Re-activate
    rv = client.post(f'/inventory/suppliers/{sid}/deactivate')
    assert rv.status_code == 302

    with app.app_context():
        sup = db.session.get(Supplier, sid)
        assert sup.is_active == 1


def test_supplier_detail_api(app_context):
    """Test the supplier detail JSON API endpoint."""
    app, client = app_context
    client.post('/auth/login', data={'email': 'admin@pos.com', 'password': 'password123'})

    from app.models import Supplier
    from extensions import db

    with app.app_context():
        s = Supplier(name='Detail Test Supplier', contact_name='Bob', phone='555', email='bob@test.com',
                     address='456 Oak Ave', notes='Special handling', is_preferred=1, is_active=1)
        db.session.add(s)
        db.session.commit()
        sid = s.supplier_id

    rv = client.get(f'/inventory/suppliers/{sid}')
    assert rv.status_code == 200

    data = rv.get_json()
    assert data['name'] == 'Detail Test Supplier'
    assert data['contact_name'] == 'Bob'
    assert data['notes'] == 'Special handling'
    assert data['is_preferred'] == 1
    assert 'recent_pos' in data
    assert 'ingredients_supplied' in data
    assert 'total_spend_cents' in data
    assert 'open_pos_count' in data
