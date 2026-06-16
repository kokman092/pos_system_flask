import datetime
from extensions import db
from sqlalchemy import CheckConstraint, Index, UniqueConstraint

# DOMAIN 3 — Operations

class RestaurantTable(db.Model):
    __tablename__ = 'restaurant_tables'
    table_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_table_branch'))
    table_number = db.Column(db.String(10), nullable=False)
    capacity = db.Column(db.Integer, default=4)
    status = db.Column(db.String(15), CheckConstraint("status IN ('available','occupied','reserved','cleaning')", name='chk_table_status'), default='available')
    is_active = db.Column(db.SmallInteger, default=1, nullable=False)
    location = db.Column(db.String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint('branch_id', 'table_number', name='uq_branch_table'),
    )

    def __repr__(self):
        return f'<RestaurantTable {self.table_number}>'

class Reservation(db.Model):
    __tablename__ = 'reservations'
    reservation_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_res_branch'))
    table_id = db.Column(db.Integer, db.ForeignKey('restaurant_tables.table_id', name='fk_res_table'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(255))
    customer_phone = db.Column(db.String(20))
    party_size = db.Column(db.Integer, nullable=False)
    reserved_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(15), CheckConstraint("status IN ('pending','confirmed','seated','cancelled','no_show')", name='chk_res_status'), default='pending')
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index(
            'uq_table_time_branch',
            'table_id', 'reserved_at', 'branch_id',
            unique=True,
            sqlite_where=db.text("status != 'cancelled'"),
            postgresql_where=db.text("status != 'cancelled'")
        ),
    )

    def __repr__(self):
        return f'<Reservation {self.customer_name}>'


    table = db.relationship('RestaurantTable', backref='reservations', foreign_keys=[table_id])

class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_order_branch'))
    table_id = db.Column(db.Integer, db.ForeignKey('restaurant_tables.table_id', name='fk_order_table'), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_order_employee'))
    order_type = db.Column(db.String(15), CheckConstraint("order_type IN ('dine_in','takeaway','delivery')", name='chk_order_type'), default='dine_in')
    status = db.Column(db.String(20), CheckConstraint("status IN ('open','confirmed','served','paid','cancelled','void')", name='chk_order_status'), default='open')
    pax = db.Column(db.Integer, default=1)
    discount_cents = db.Column(db.Integer, default=0)
    notes = db.Column(db.String(500))
    seat_count = db.Column(db.Integer, default=1)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id', name='fk_order_customer'), nullable=True)
    version = db.Column(db.Integer, default=1, nullable=False)  # Optimistic locking
    opened_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship('OrderItem', backref='order')
    payments = db.relationship('Payment', backref='order')
    table = db.relationship('RestaurantTable', foreign_keys=[table_id])

    __table_args__ = (
        Index('ix_orders_branch_status', 'branch_id', 'status'),
        Index('ix_orders_opened_at', 'opened_at'),
        Index('ix_orders_branch_opened_at', 'branch_id', 'opened_at'),
        Index('ix_orders_branch_status_opened_at', 'branch_id', 'status', 'opened_at'),
    )

    def to_dict(self):
        return {
            'order_id': self.order_id,
            'branch_id': self.branch_id,
            'table_id': self.table_id,
            'employee_id': self.employee_id,
            'customer_id': self.customer_id,
            'order_type': self.order_type,
            'status': self.status,
            'pax': self.pax,
            'discount_cents': self.discount_cents,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'version': self.version
        }

    def __repr__(self):
        return f'<Order {self.order_id}>'

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    order_item_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', name='fk_oi_order'))
    item_id = db.Column(db.Integer, db.ForeignKey('menu_items.item_id', name='fk_oi_item'))
    quantity = db.Column(db.Integer, CheckConstraint('quantity > 0', name='chk_oi_quantity'), default=1)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    discount_cents = db.Column(db.Integer, default=0)
    notes = db.Column(db.String(255))
    seat_number = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(15), CheckConstraint("status IN ('pending','kitchen','served','cancelled')", name='chk_oi_status'), default='pending')
    sent_at = db.Column(db.DateTime, nullable=True)
    served_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        Index('ix_oi_order_id', 'order_id'),
        Index('ix_oi_status', 'status'),
        Index('ix_order_items_order_item_status', 'order_id', 'item_id', 'status'),
    )

    menu_item = db.relationship('MenuItem', foreign_keys=[item_id])

    def to_dict(self):
        return {
            'order_item_id': self.order_item_id,
            'order_id': self.order_id,
            'item_id': self.item_id,
            'quantity': self.quantity
        }

    def __repr__(self):
        return f'<OrderItem {self.order_item_id}>'

