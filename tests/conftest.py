import pytest
from app import create_app
from extensions import db

@pytest.fixture(scope="session")
def app_context():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        
        # Seed permissions and roles in testing DB
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
            perm = Permission(permission_key=key, module=mod, action=act)
            db.session.add(perm)
            db.session.flush()
            permissions_dict[key] = perm
        
        default_roles_data = [
            ("Owner / Admin", "Full system administrator access", 1, [
                key for key, _, _ in permissions_data
            ]),
            ("Branch Manager", "Manage branch POS, inventory, reports, and purchase orders", 1, [
                "dashboard:view",
                "pos:create_sale", "pos:apply_discount", "pos:void_bill", "pos:refund", "pos:open_drawer", "pos:shift_close", "pos:view",
                "inventory:view", "inventory:add_stock", "inventory:adjust_stock", "inventory:count_stock", "inventory:view_history",
                "ingredients:add", "ingredients:edit", "ingredients:deactivate",
                "suppliers:view", "suppliers:create", "suppliers:edit", "suppliers:delete",
                "purchasing:create", "purchasing:approve", "purchasing:cancel", "purchasing:receive", "purchasing:view",
                "reports:sales", "reports:inventory", "reports:purchasing", "reports:export",
                "users:manage"
            ]),
            ("Cashier", "Handle POS operations, checkout, and receipt printing", 1, [
                "pos:create_sale", "pos:apply_discount", "pos:open_drawer", "pos:shift_close", "pos:view"
            ]),
            ("Inventory Clerk / Purchaser", "Manage inventory items, suppliers, purchase orders, and receive deliveries", 1, [
                "inventory:view", "inventory:add_stock", "inventory:adjust_stock", "inventory:count_stock", "inventory:view_history",
                "ingredients:add", "ingredients:edit", "ingredients:deactivate",
                "suppliers:view", "suppliers:create", "suppliers:edit", "suppliers:delete",
                "purchasing:create", "purchasing:cancel", "purchasing:receive", "purchasing:view",
                "reports:inventory", "reports:purchasing"
            ]),
            ("Kitchen / Staff", "Kitchen Display System status updates and basic views", 1, [
                "pos:view"
            ])
        ]
        
        for rname, desc, is_sys, perm_keys in default_roles_data:
            role_rec = Role(role_name=rname, description=desc, is_system_role=is_sys)
            db.session.add(role_rec)
            db.session.flush()
            role_rec.permissions = [permissions_dict[k] for k in perm_keys if k in permissions_dict]
        
        db.session.commit()
        
        with app.test_client() as client:
            yield app, client
        db.drop_all()
