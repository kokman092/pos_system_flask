import os
import random
from datetime import datetime, timedelta
from app import create_app
from extensions import db
from app.models import (
    Branch, Employee, Category, MenuItem, Ingredient, ItemIngredient,
    RestaurantTable, Customer, Modifier, Order, OrderItem, Payment, WasteLog,
    Reservation
)

from extensions import bcrypt

def seed_database():
    app = create_app('development')
    with app.app_context():
        print("Starting comprehensive seed process...")
        
        # 1. Branch
        branch = Branch.query.filter_by(name="Main Branch").first()
        if not branch:
            branch = Branch(name="Main Branch", location="Downtown", is_active=1)
            db.session.add(branch)
            db.session.commit()
            print("Created Main Branch")

        # 1b. Seed Roles & Permissions
        from app.models import Role, Permission
        
        permissions_data = [
            ("dashboard:view", "dashboard", "view"),
            ("pos:create_sale", "pos", "create_sale"),
            ("pos:apply_discount", "pos", "apply_discount"),
            ("pos:void_bill", "pos", "void_bill"),
            ("pos:refund", "pos", "refund"),
            ("pos:open_drawer", "pos", "open_drawer"),
            ("pos:shift_close", "pos", "shift_close"),
            ("pos:view", "pos", "view"),
            ("inventory:view", "inventory", "view"),
            ("inventory:add_stock", "inventory", "add_stock"),
            ("inventory:adjust_stock", "inventory", "adjust_stock"),
            ("inventory:count_stock", "inventory", "count_stock"),
            ("inventory:view_history", "inventory", "view_history"),
            ("ingredients:add", "ingredients", "add"),
            ("ingredients:edit", "ingredients", "edit"),
            ("ingredients:deactivate", "ingredients", "deactivate"),
            ("suppliers:view", "suppliers", "view"),
            ("suppliers:create", "suppliers", "create"),
            ("suppliers:edit", "suppliers", "edit"),
            ("suppliers:delete", "suppliers", "delete"),
            ("purchasing:create", "purchasing", "create"),
            ("purchasing:approve", "purchasing", "approve"),
            ("purchasing:cancel", "purchasing", "cancel"),
            ("purchasing:receive", "purchasing", "receive"),
            ("purchasing:view", "purchasing", "view"),
            ("reports:sales", "reports", "sales"),
            ("reports:inventory", "reports", "inventory"),
            ("reports:purchasing", "reports", "purchasing"),
            ("reports:export", "reports", "export"),
            ("users:manage", "users", "manage"),
            ("roles:manage", "roles", "manage"),
            ("settings:manage", "settings", "manage"),
            ("audit_logs:view", "audit_logs", "view")
        ]
        
        permissions_dict = {}
        for key, mod, act in permissions_data:
            perm = Permission.query.filter_by(permission_key=key).first()
            if not perm:
                perm = Permission(permission_key=key, module=mod, action=act)
                db.session.add(perm)
                db.session.flush()
            permissions_dict[key] = perm
        db.session.commit()
        print("Permissions confirmed.")
        
        # Default Roles
        default_roles_data = [
            ("Owner / Admin", "Full system administrator access", 1, "admin", [
                key for key, _, _ in permissions_data
            ]),
            ("Branch Manager", "Manage branches, inventory, POS, reports, and purchase orders", 1, "manager", [
                "dashboard:view",
                "pos:create_sale", "pos:apply_discount", "pos:void_bill", "pos:refund", "pos:open_drawer", "pos:shift_close", "pos:view",
                "inventory:view", "inventory:add_stock", "inventory:adjust_stock", "inventory:count_stock", "inventory:view_history",
                "ingredients:add", "ingredients:edit", "ingredients:deactivate",
                "suppliers:view", "suppliers:create", "suppliers:edit", "suppliers:delete",
                "purchasing:create", "purchasing:approve", "purchasing:cancel", "purchasing:receive", "purchasing:view",
                "reports:sales", "reports:inventory", "reports:purchasing", "reports:export",
                "users:manage"
            ]),
            ("Cashier", "Handle POS operations, checkout, and receipt printing", 1, "cashier", [
                "pos:create_sale", "pos:apply_discount", "pos:open_drawer", "pos:shift_close", "pos:view"
            ]),
            ("Inventory Clerk / Purchaser", "Manage inventory items, suppliers, purchase orders, and receive deliveries", 1, "purchaser", [
                "inventory:view", "inventory:add_stock", "inventory:adjust_stock", "inventory:count_stock", "inventory:view_history",
                "ingredients:add", "ingredients:edit", "ingredients:deactivate",
                "suppliers:view", "suppliers:create", "suppliers:edit", "suppliers:delete",
                "purchasing:create", "purchasing:cancel", "purchasing:receive", "purchasing:view",
                "reports:inventory", "reports:purchasing"
            ]),
            ("Kitchen / Staff", "Kitchen Display System status updates and basic views", 1, "kitchen", [
                "pos:view"
            ])
        ]
        
        roles_obj = {}
        for rname, desc, is_sys, slug, perm_keys in default_roles_data:
            role_rec = Role.query.filter_by(role_name=rname).first()
            if not role_rec:
                role_rec = Role(role_name=rname, description=desc, is_system_role=is_sys, role_slug=slug)
                db.session.add(role_rec)
            else:
                role_rec.role_slug = slug
            db.session.flush()
            
            # Associate permissions
            role_rec.permissions = [permissions_dict[k] for k in perm_keys if k in permissions_dict]
            roles_obj[rname] = role_rec
        db.session.commit()
        print("Roles confirmed.")
        
        # 2. Employees
        admin_role = roles_obj["Owner / Admin"]
        manager_role = roles_obj["Branch Manager"]
        cashier_role = roles_obj["Cashier"]
        purchaser_role = roles_obj["Inventory Clerk / Purchaser"]
        kitchen_role = roles_obj["Kitchen / Staff"]
        
        if not Employee.query.filter_by(email="admin@pos.com").first():
            pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
            db.session.add(Employee(
                branch_id=branch.branch_id, full_name="System Admin", email="admin@pos.com",
                password_hash=pw_hash, role_id=admin_role.role_id, is_active=1, email_verified=1
            ))
            
        if not Employee.query.filter_by(email="manager@pos.com").first():
            pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
            db.session.add(Employee(
                branch_id=branch.branch_id, full_name="Store Manager", email="manager@pos.com",
                password_hash=pw_hash, role_id=manager_role.role_id, is_active=1, email_verified=1
            ))
            
        if not Employee.query.filter_by(email="cashier@pos.com").first():
            pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
            db.session.add(Employee(
                branch_id=branch.branch_id, full_name="Cashier User", email="cashier@pos.com",
                password_hash=pw_hash, role_id=cashier_role.role_id, is_active=1, email_verified=1
            ))
            
        if not Employee.query.filter_by(email="purchaser@pos.com").first():
            pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
            db.session.add(Employee(
                branch_id=branch.branch_id, full_name="Purchaser User", email="purchaser@pos.com",
                password_hash=pw_hash, role_id=purchaser_role.role_id, is_active=1, email_verified=1
            ))
            
        if not Employee.query.filter_by(email="kitchen@pos.com").first():
            pw_hash = bcrypt.generate_password_hash("password123").decode('utf-8')
            db.session.add(Employee(
                branch_id=branch.branch_id, full_name="Kitchen Staff", email="kitchen@pos.com",
                password_hash=pw_hash, role_id=kitchen_role.role_id, is_active=1, email_verified=1
            ))
        db.session.commit()
        print("Employees confirmed.")

        # 3. Customer
        customer = Customer.query.filter_by(phone="555-0199").first()
        if not customer:
            customer = Customer(name="John Doe", phone="555-0199", email="john@example.com", points_balance=250)
            db.session.add(customer)
            db.session.commit()

        # 4. Tables (10 tables)
        if not RestaurantTable.query.filter_by(branch_id=branch.branch_id).first():
            for i in range(1, 11):
                db.session.add(RestaurantTable(branch_id=branch.branch_id, table_number=f"T{i}", capacity=random.choice([2,4,6]), status='available'))
            db.session.commit()
            print("Tables created.")

        # 5. Categories
        cats_data = [
            ("Burgers", "img/categories/burgers.jpg"),
            ("Drinks", "img/categories/drinks.jpg"),
            ("Desserts", "img/categories/desserts.jpg"),
            ("Mains", "img/categories/mains.jpg")
        ]
        categories = {}
        for cname, cimg in cats_data:
            cat = Category.query.filter_by(name=cname).first()
            if not cat:
                cat = Category(name=cname, image_path=cimg, is_active=1)
                db.session.add(cat)
                db.session.flush()
            categories[cname] = cat
        db.session.commit()

        # 6. Menu Items
        items_data = [
            ("Classic Burger", categories["Burgers"].category_id, 1200, "img/menu/burger-classic.jpg"),
            ("Wagyu Burger", categories["Burgers"].category_id, 1850, "img/placeholders/menu-placeholder.jpg"),
            ("Cheese Burger", categories["Burgers"].category_id, 1350, "img/placeholders/menu-placeholder.jpg"),
            ("Iced Coffee", categories["Drinks"].category_id, 450, "img/menu/iced-coffee.jpg"),
            ("Lemonade", categories["Drinks"].category_id, 350, "img/placeholders/menu-placeholder.jpg"),
            ("Soda", categories["Drinks"].category_id, 250, "img/placeholders/menu-placeholder.jpg"),
            ("Caesar Salad", categories["Mains"].category_id, 900, "img/menu/caesar-salad.jpg"),
            ("Margherita Pizza", categories["Mains"].category_id, 1400, "img/menu/margherita-pizza.jpg"),
            ("Grilled Salmon", categories["Mains"].category_id, 2200, "img/menu/grilled-salmon.jpg"),
            ("Steak Frites", categories["Mains"].category_id, 2800, "img/placeholders/menu-placeholder.jpg"),
            ("Chocolate Brownie", categories["Desserts"].category_id, 650, "img/menu/brownie.jpg"),
            ("Cheesecake", categories["Desserts"].category_id, 750, "img/placeholders/menu-placeholder.jpg")
        ]
        
        menu_items_obj = []
        for name, cid, price, img in items_data:
            item = MenuItem.query.filter_by(name=name).first()
            if not item:
                item = MenuItem(branch_id=branch.branch_id, category_id=cid, name=name, price_cents=price, tax_pct=10, image_path=img, is_available=1, is_active=1)
                db.session.add(item)
                db.session.flush()
            menu_items_obj.append(item)
        db.session.commit()
        
        # 7. Ingredients & Low Stock
        ingredients_data = [
            ("Beef Patty", "pcs", 50, 100, 200, "img/ingredients/beef-patty.png"),  # Low stock
            ("Wagyu Beef", "pcs", 5, 20, 500, "img/ingredients/wagyu-beef.png"),    # Low stock
            ("Lettuce", "kg", 1.5, 5.0, 300, "img/ingredients/lettuce.png"),     # Low stock
            ("Tomato", "kg", 15.0, 10.0, 250, "img/ingredients/tomato.png"),    # OK stock
            ("Coffee Beans", "kg", 8.0, 5.0, 1200, "img/ingredients/coffee-beans.png") # OK stock
        ]
        ingredients_obj = []
        for name, unit, qty, reorder, cost, img in ingredients_data:
            ing = Ingredient.query.filter_by(name=name).first()
            if not ing:
                ing = Ingredient(name=name, unit=unit, qty_in_stock=qty, reorder_level=reorder, cost_per_unit_cents=cost, branch_id=branch.branch_id, image_path=img)
                db.session.add(ing)
                db.session.flush()
            else:
                ing.image_path = img
            ingredients_obj.append(ing)
        db.session.commit()
        
        # 8. Waste Logs
        if WasteLog.query.count() < 5:
            for _ in range(5):
                db.session.add(WasteLog(
                    branch_id=branch.branch_id,
                    ingredient_id=random.choice(ingredients_obj).ingredient_id,
                    qty=random.uniform(0.5, 2.0),
                    unit_cost_cents=random.randint(200, 800),
                    reason=random.choice(["Spoiled", "Dropped", "Expired"]),
                    recorded_by=1, # Admin
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 14))
                ))
            db.session.commit()

        # 9. Orders (14 days historical data)
        # Avoid seeding multiple times
        if Order.query.count() < 20:
            print("Generating 14 days of order history... this may take a moment.")
            now = datetime.utcnow()
            for day_offset in range(14):
                base_date = now - timedelta(days=13 - day_offset)
                
                # Create 3-8 orders per day
                for _ in range(random.randint(3, 8)):
                    hour_offset = random.randint(10, 22)
                    opened_at = base_date.replace(hour=hour_offset, minute=random.randint(0, 59))
                    
                    order = Order(
                        branch_id=branch.branch_id,
                        employee_id=1,
                        order_type=random.choice(['dine_in', 'takeaway']),
                        status='paid',
                        opened_at=opened_at,
                        closed_at=opened_at + timedelta(minutes=random.randint(15, 60))
                    )
                    db.session.add(order)
                    db.session.flush()
                    
                    # Order Items
                    total_cents = 0
                    for _ in range(random.randint(1, 4)):
                        item = random.choice(menu_items_obj)
                        qty = random.randint(1, 2)
                        total_cents += item.price_cents * qty
                        
                        db.session.add(OrderItem(
                            order_id=order.order_id,
                            item_id=item.item_id,
                            quantity=qty,
                            unit_price_cents=item.price_cents,
                            status='served'
                        ))
                    
                    # Payment
                    db.session.add(Payment(
                        order_id=order.order_id,
                        amount_cents=total_cents,
                        method=random.choice(['cash', 'card', 'qr_code']),
                        paid_at=order.closed_at
                    ))
            db.session.commit()
            print("Historical orders generated.")

        # 10. Seed Reservations
        tomorrow = datetime.utcnow().date() + timedelta(days=1)
        res_time = datetime.combine(tomorrow, datetime.min.time()).replace(hour=18, minute=0)

        existing = Reservation.query.filter_by(
            customer_phone="+15555551234",
            reserved_at=res_time,
            branch_id=branch.branch_id
        ).first()

        if not existing:
            t = RestaurantTable.query.filter_by(branch_id=branch.branch_id).first()
            table_id = t.table_id if t else None

            db.session.add(Reservation(
                branch_id=branch.branch_id,
                customer_name="George Harrison",
                customer_email="george@beatles.com",
                customer_phone="+15555551234",
                party_size=4,
                reserved_at=res_time,
                table_id=table_id,
                notes="Prefers table near window",
                status="confirmed"
            ))
            db.session.commit()
            print("Seeded George Harrison reservation.")

        # 11. Seed Suppliers and Purchase Orders
        from app.models import Supplier, PurchaseOrder, PurchaseOrderItem, SupplierPriceHistory
        supplier = Supplier.query.filter_by(name="Global Foods Inc").first()
        if not supplier:
            supplier = Supplier(
                name="Global Foods Inc",
                contact_name="Sarah Connor",
                phone="555-0921",
                email="orders@globalfoods.com",
                address="100 Logistics Blvd, Chicago IL",
                image_path="img/placeholders/menu-placeholder.jpg",
                is_active=1
            )
            db.session.add(supplier)
            
            supplier2 = Supplier(
                name="Fresh Farms Local",
                contact_name="Bob Miller",
                phone="555-8712",
                email="fresh@farmslocal.com",
                address="42 Country Road, Naperville IL",
                image_path="img/placeholders/menu-placeholder.jpg",
                is_active=1
            )
            db.session.add(supplier2)
            db.session.commit()
            print("Seeded suppliers.")

            # Create a draft and received purchase order
            po1 = PurchaseOrder(
                branch_id=branch.branch_id,
                supplier_id=supplier.supplier_id,
                po_number=f"PO-{branch.branch_id}-20260615-0001",
                status='draft',
                notes="Weekly bulk meat order",
                created_by=1,
                created_at=datetime.utcnow() - timedelta(days=2)
            )
            db.session.add(po1)
            db.session.flush()

            po_item1 = PurchaseOrderItem(
                purchase_order_id=po1.purchase_order_id,
                ingredient_id=ingredients_obj[0].ingredient_id, # Beef Patty
                ordered_qty=100.000,
                received_qty=0.000,
                unit_cost_cents=200,
                line_total_cents=20000
            )
            db.session.add(po_item1)

            # Let's seed a received order to populate analytics
            po2 = PurchaseOrder(
                branch_id=branch.branch_id,
                supplier_id=supplier2.supplier_id,
                po_number=f"PO-{branch.branch_id}-20260614-0001",
                status='received',
                notes="Initial fresh produce delivery",
                created_by=1,
                ordered_at=datetime.utcnow() - timedelta(days=3),
                expected_at=datetime.utcnow() - timedelta(days=2),
                received_at=datetime.utcnow() - timedelta(days=2),
                created_at=datetime.utcnow() - timedelta(days=3)
            )
            db.session.add(po2)
            db.session.flush()

            po_item2 = PurchaseOrderItem(
                purchase_order_id=po2.purchase_order_id,
                ingredient_id=ingredients_obj[2].ingredient_id, # Lettuce
                ordered_qty=20.000,
                received_qty=20.000,
                unit_cost_cents=150,
                line_total_cents=3000
            )
            db.session.add(po_item2)

            # Record Price History for the received items
            sph = SupplierPriceHistory(
                supplier_id=supplier2.supplier_id,
                ingredient_id=ingredients_obj[2].ingredient_id,
                unit_cost_cents=150,
                recorded_at=datetime.utcnow() - timedelta(days=2)
            )
            db.session.add(sph)
            
            db.session.commit()
            print("Seeded purchase orders and price histories.")

        print("Seed completed successfully.")

if __name__ == "__main__":
    seed_database()
