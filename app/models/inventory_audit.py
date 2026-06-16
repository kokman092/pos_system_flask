import datetime
from extensions import db
from sqlalchemy import CheckConstraint, Index

# DOMAIN 11 — Inventory Audit

class WasteLog(db.Model):
    __tablename__ = 'waste_logs'
    waste_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_wastelog_branch'))
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id', name='fk_wastelog_ingredient'))
    qty = db.Column(db.Numeric(12, 3), nullable=False)
    unit_cost_cents = db.Column(db.Integer, default=0)
    reason = db.Column(db.String(255))
    recorded_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_wastelog_emp'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index('ix_waste_logs_branch_date', 'branch_id', 'created_at'),
    )

    def __repr__(self):
        return f'<WasteLog {self.waste_id}>'

    recorder = db.relationship('Employee', foreign_keys=[recorded_by])

class InventoryCountSession(db.Model):
    __tablename__ = 'inventory_count_sessions'
    session_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_invsession_branch'))
    session_name = db.Column(db.String(100))
    started_by = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_invsession_emp'))
    started_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(15), CheckConstraint("status IN ('open','completed','cancelled')", name='chk_invsession_status'))

    def __repr__(self):
        return f'<InventoryCountSession {self.session_id}>'

    count_items = db.relationship('InventoryCountItem', backref='session')

class InventoryCountItem(db.Model):
    __tablename__ = 'inventory_count_items'
    count_item_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('inventory_count_sessions.session_id', name='fk_invitem_session'))
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id', name='fk_invitem_ingredient'))
    system_qty = db.Column(db.Numeric(12, 3))
    counted_qty = db.Column(db.Numeric(12, 3))
    variance_qty = db.Column(db.Numeric(12, 3))
    variance_cost_cents = db.Column(db.Integer)

    def __repr__(self):
        return f'<InventoryCountItem {self.count_item_id}>'

    ingredient = db.relationship('Ingredient', foreign_keys=[ingredient_id])

