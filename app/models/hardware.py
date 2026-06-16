import datetime
from extensions import db
from sqlalchemy import CheckConstraint

# DOMAIN 10 — Hardware

class PrinterConfig(db.Model):
    __tablename__ = 'printer_configs'
    printer_config_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_printer_branch'))
    printer_role = db.Column(db.String(20), CheckConstraint("printer_role IN ('kitchen','receipt','bar')", name='chk_printer_role'))
    name = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    port = db.Column(db.Integer, default=9100)
    profile = db.Column(db.String(50), default='epson')
    is_enabled = db.Column(db.SmallInteger, default=1)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<PrinterConfig {self.name}>'

    logs = db.relationship('PrintLog', backref='printer')

class PrintLog(db.Model):
    __tablename__ = 'print_logs'
    print_log_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_printlog_branch'))
    printer_config_id = db.Column(db.Integer, db.ForeignKey('printer_configs.printer_config_id', name='fk_printlog_printer'), nullable=True)
    reference_type = db.Column(db.String(30))
    reference_id = db.Column(db.Integer)
    status = db.Column(db.String(15), CheckConstraint("status IN ('queued','sent','failed')", name='chk_printlog_status'))
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<PrintLog {self.print_log_id}>'

