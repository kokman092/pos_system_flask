import datetime
from extensions import db
from sqlalchemy import CheckConstraint

# DOMAIN 8 — Loyalty

class Customer(db.Model):
    __tablename__ = 'customers'
    customer_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    email = db.Column(db.String(255))
    points_balance = db.Column(db.Integer, default=0)
    total_spent_cents = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    transactions = db.relationship('LoyaltyTransaction', backref='customer')
    orders = db.relationship('Order', backref='customer')

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "points_balance": self.points_balance,
            "total_spent_cents": self.total_spent_cents,
            "member_since": self.created_at.strftime('%d %b %Y') if self.created_at else None
        }

    def __repr__(self):
        return f'<Customer {self.name}>'

class LoyaltyTransaction(db.Model):
    __tablename__ = 'loyalty_transactions'
    transaction_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.customer_id', name='fk_loyaltytx_customer'))
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', name='fk_loyaltytx_order'), nullable=True)
    points_earned = db.Column(db.Integer, default=0)
    points_redeemed = db.Column(db.Integer, default=0)
    points_balance_after = db.Column(db.Integer, default=0)
    reason = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    @property
    def transaction_type(self):
        return 'earned' if self.points_earned > 0 else 'redeemed'

    def __repr__(self):
        return f'<LoyaltyTransaction {self.transaction_id}>'

    order = db.relationship('Order', foreign_keys=[order_id])

