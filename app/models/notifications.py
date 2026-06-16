import datetime
from extensions import db
from sqlalchemy import CheckConstraint, Index

# DOMAIN 6 — Notifications

class EmailRecipient(db.Model):
    __tablename__ = 'email_recipients'
    recipient_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_emailrec_branch'), nullable=True)
    recipient_type = db.Column(db.String(20), CheckConstraint("recipient_type IN ('customer','manager','supplier','staff')", name='chk_emailrec_type'))
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    is_subscribed = db.Column(db.SmallInteger, default=1)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<EmailRecipient {self.email}>'

class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'
    template_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trigger_event = db.Column(db.String(50), CheckConstraint("trigger_event IN ('order_paid','low_stock','shift_report','reservation_confirm','order_cancelled','promotion','password_reset')", name='chk_emailtpl_trigger'))
    subject = db.Column(db.String(255), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.SmallInteger, default=1)

    def __repr__(self):
        return f'<EmailTemplate {self.name}>'

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    email_log_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('email_templates.template_id', name='fk_emaillog_template'), nullable=True)
    recipient_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    reference_type = db.Column(db.String(30))
    reference_id = db.Column(db.Integer)
    status = db.Column(db.String(15), CheckConstraint("status IN ('pending','sent','failed','bounced','opened')", name='chk_emaillog_status'), default='pending')
    retry_count = db.Column(db.Integer, default=0)
    sent_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<EmailLog {self.email_log_id}>'

    __table_args__ = (
        Index('ix_emaillog_status', 'status'),
    )

