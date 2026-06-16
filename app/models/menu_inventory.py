import datetime
from extensions import db
from sqlalchemy import CheckConstraint, Index, PrimaryKeyConstraint

# DOMAIN 2 — Menu & Inventory

class Category(db.Model):
    __tablename__ = 'categories'
    category_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.SmallInteger, default=1)
    image_path = db.Column(db.String(255), nullable=True)

    items = db.relationship('MenuItem', backref='category')

    def __repr__(self):
        return f'<Category {self.name}>'

class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    item_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id', name='fk_menuitem_category'))
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500))
    price_cents = db.Column(db.Integer, CheckConstraint('price_cents >= 0', name='chk_menuitem_price'), nullable=False)
    tax_pct = db.Column(db.Numeric(5, 2), default=0.00)
    is_available = db.Column(db.SmallInteger, default=1)
    is_active = db.Column(db.SmallInteger, default=1)
    image_path = db.Column(db.String(255), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_menuitem_branch'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # modifiers could be related via an association table or directly if 1-to-many, but instructions say Modifier isn't directly FK'd.
    # We will assume relationship setup later if needed.

    def to_dict(self):
        return {
            'item_id': self.item_id,
            'category_id': self.category_id,
            'name': self.name,
            'price_cents': self.price_cents,
            'is_available': self.is_available,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f'<MenuItem {self.name}>'

    recipes = db.relationship('ItemIngredient', backref='menu_item', foreign_keys='ItemIngredient.item_id')

class Ingredient(db.Model):
    __tablename__ = 'ingredients'
    ingredient_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    qty_in_stock = db.Column(db.Numeric(12, 3), CheckConstraint('qty_in_stock >= 0', name='chk_ingredient_qty'), default=0)
    reorder_level = db.Column(db.Numeric(12, 3), default=0)
    cost_per_unit_cents = db.Column(db.Integer, default=0)
    image_path = db.Column(db.String(255), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_ingredient_branch'))
    is_active = db.Column(db.SmallInteger, default=1)
    default_supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id', name='fk_ingredient_supplier'), nullable=True)
    default_supplier = db.relationship('Supplier', foreign_keys=[default_supplier_id])

    __table_args__ = (
        Index('ix_ingredients_branch_stock', 'branch_id', 'qty_in_stock'),
    )

    def __repr__(self):
        return f'<Ingredient {self.name}>'

    batches = db.relationship('StockBatch', backref='ingredient')
    recipes = db.relationship('ItemIngredient', backref='ingredient', foreign_keys='ItemIngredient.ingredient_id')
    waste_logs = db.relationship('WasteLog', backref='ingredient')

class ItemIngredient(db.Model):
    __tablename__ = 'item_ingredients'
    item_id = db.Column(db.Integer, db.ForeignKey('menu_items.item_id', name='fk_ii_menuitem'))
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id', name='fk_ii_ingredient'))
    qty_used = db.Column(db.Numeric(10, 4), CheckConstraint('qty_used > 0', name='chk_ii_qty_used'), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('item_id', 'ingredient_id', name='pk_item_ingredients'),
    )

    def __repr__(self):
        return f'<ItemIngredient item_id={self.item_id} ingredient_id={self.ingredient_id}>'

class StockBatch(db.Model):
    __tablename__ = 'stock_batches'
    batch_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id', name='fk_stockbatch_ingredient'))
    qty_received = db.Column(db.Numeric(12, 3), nullable=False)
    qty_remaining = db.Column(db.Numeric(12, 3), nullable=False)
    cost_per_unit_cents = db.Column(db.Integer, nullable=False)
    received_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    supplier_ref = db.Column(db.String(100))
    notes = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<StockBatch {self.batch_id}>'

    __table_args__ = (
        Index('ix_batch_ingredient_received', 'ingredient_id', 'received_at'),
    )

class Modifier(db.Model):
    __tablename__ = 'modifiers'
    modifier_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price_cents = db.Column(db.Integer, default=0)
    group_name = db.Column(db.String(50))
    is_active = db.Column(db.SmallInteger, default=1)

    def __repr__(self):
        return f'<Modifier {self.name}>'


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    supplier_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(100))
    address = db.Column(db.String(255))
    image_path = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_preferred = db.Column(db.SmallInteger, default=0, nullable=False)
    is_active = db.Column(db.SmallInteger, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    purchase_orders = db.relationship('PurchaseOrder', backref='supplier')
    price_history = db.relationship('SupplierPriceHistory', backref='supplier')

    def __repr__(self):
        return f'<Supplier {self.name}>'


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    purchase_order_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_po_branch'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id', name='fk_po_supplier'))
    po_number = db.Column(db.String(30), nullable=False, unique=True)
    status = db.Column(db.String(30), default='draft')  # draft, approved, ordered, partially_received, received, cancelled
    ordered_at = db.Column(db.DateTime, nullable=True)
    expected_at = db.Column(db.DateTime, nullable=True)
    received_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_po_creator'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_po_approver'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    received_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_po_receiver'), nullable=True)
    invoice_ref = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    items = db.relationship('PurchaseOrderItem', backref='purchase_order', cascade="all, delete-orphan")

    creator = db.relationship('Employee', foreign_keys=[created_by], backref='created_pos')
    approver = db.relationship('Employee', foreign_keys=[approved_by], backref='approved_pos')
    receiver = db.relationship('Employee', foreign_keys=[received_by], backref='received_pos')

    def __repr__(self):
        return f'<PurchaseOrder {self.po_number}>'


class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    purchase_order_item_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.purchase_order_id', name='fk_poi_po'))
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id', name='fk_poi_ingredient'))
    ordered_qty = db.Column(db.Numeric(12, 3), nullable=False)
    received_qty = db.Column(db.Numeric(12, 3), default=0.0)
    unit_cost_cents = db.Column(db.Integer, nullable=False)
    line_total_cents = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(255))

    ingredient = db.relationship('Ingredient', foreign_keys=[ingredient_id])

    def __repr__(self):
        return f'<PurchaseOrderItem {self.purchase_order_item_id}>'


class SupplierPriceHistory(db.Model):
    __tablename__ = 'supplier_price_history'
    supplier_price_history_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.supplier_id', name='fk_sph_supplier'))
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id', name='fk_sph_ingredient'))
    unit_cost_cents = db.Column(db.Integer, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    ingredient = db.relationship('Ingredient', foreign_keys=[ingredient_id])

    def __repr__(self):
        return f'<SupplierPriceHistory {self.supplier_price_history_id}>'

