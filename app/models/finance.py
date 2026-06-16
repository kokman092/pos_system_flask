import datetime
from extensions import db
from sqlalchemy import CheckConstraint, Index

# DOMAIN 4 — Finance

class Payment(db.Model):
    __tablename__ = 'payments'
    payment_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.order_id', name='fk_payment_order'))
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_payment_employee'))
    method = db.Column(db.String(20), CheckConstraint("method IN ('cash','card','qr_code','voucher','split')", name='chk_payment_method'))
    amount_cents = db.Column(db.Integer, CheckConstraint('amount_cents > 0', name='chk_payment_amount'), nullable=False)
    tendered_cents = db.Column(db.Integer, nullable=True)
    change_cents = db.Column(db.Integer, default=0)
    reference_no = db.Column(db.String(100))
    split_reference_id = db.Column(db.Integer, db.ForeignKey('payments.payment_id', name='fk_payment_split'), nullable=True)
    paid_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_voided = db.Column(db.SmallInteger, default=0)

    cashier = db.relationship('Employee', foreign_keys=[employee_id])

    __table_args__ = (
        Index('ix_payments_order_id', 'order_id'),
        Index('ix_payments_order_paid_method', 'order_id', 'paid_at', 'method'),
    )

    def to_dict(self):
        return {
            'payment_id': self.payment_id,
            'order_id': self.order_id,
            'amount_cents': self.amount_cents,
            'method': self.method
        }

    def __repr__(self):
        return f'<Payment {self.payment_id}>'

