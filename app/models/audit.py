import datetime
from extensions import db
from sqlalchemy import CheckConstraint, Index

# DOMAIN 5 — Audit

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    log_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(10), CheckConstraint("action IN ('INSERT','UPDATE','DELETE')", name='chk_audit_action'))
    changed_by = db.Column(db.Integer, nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)

    def __repr__(self):
        return f'<AuditLog {self.log_id}>'

    __table_args__ = (
        Index('ix_audit_table_record', 'table_name', 'record_id'),
    )

