import datetime
from extensions import db
from sqlalchemy import CheckConstraint, Index

# DOMAIN 7 — Auth

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    session_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_usersession_employee'))
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_revoked = db.Column(db.SmallInteger, CheckConstraint('is_revoked IN (0,1)', name='chk_session_revoked'), default=0)

    def __repr__(self):
        return f'<UserSession {self.session_id}>'

    __table_args__ = (
        Index('ix_session_token', 'session_token'),
    )

class EmailVerification(db.Model):
    __tablename__ = 'email_verifications'
    verify_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id', name='fk_emailver_employee'))
    token = db.Column(db.String(255), unique=True, nullable=False)
    token_type = db.Column(db.String(20), CheckConstraint("token_type IN ('verify_email','reset_password','invite')", name='chk_emailver_type'))
    is_used = db.Column(db.SmallInteger, CheckConstraint('is_used IN (0,1)', name='chk_emailver_used'), default=0)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<EmailVerification {self.verify_id}>'
