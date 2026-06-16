import datetime
from extensions import db
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property

# DOMAIN 1 — Identity & Access

class Branch(db.Model):
    __tablename__ = 'branches'
    branch_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.SmallInteger, CheckConstraint('is_active IN (0,1)', name='chk_branch_is_active'), default=1)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    employees = db.relationship('Employee', backref='branch')
    tables = db.relationship('RestaurantTable', backref='branch')
    ingredients = db.relationship('Ingredient', backref='branch')
    kds_stations = db.relationship('KdsStation', backref='branch')
    printers = db.relationship('PrinterConfig', backref='branch')

    def __repr__(self):
        return f'<Branch {self.name}>'


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id', name='fk_rp_role', ondelete='CASCADE'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.permission_id', name='fk_rp_permission', ondelete='CASCADE'), primary_key=True)


class Role(db.Model):
    __tablename__ = 'roles'
    role_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    role_name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(255))
    is_system_role = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Relationships
    permissions = db.relationship('Permission', secondary='role_permissions', back_populates='roles')
    employees = db.relationship('Employee', backref='role_rel')

    def __repr__(self):
        return f'<Role {self.role_name}>'


class Permission(db.Model):
    __tablename__ = 'permissions'
    permission_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    permission_key = db.Column(db.String(100), nullable=False, unique=True)
    module = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(20), nullable=False)

    roles = db.relationship('Role', secondary='role_permissions', back_populates='permissions')

    def __repr__(self):
        return f'<Permission {self.permission_key}>'


class Employee(db.Model, UserMixin):
    __tablename__ = 'employees'
    employee_id = db.Column(db.Integer, db.Identity(), primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.branch_id', name='fk_emp_branch'))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id', name='fk_emp_role'), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True)
    email_verified = db.Column(db.SmallInteger, CheckConstraint('email_verified IN (0,1)', name='chk_emp_email_verified'), default=0)
    password_hash = db.Column(db.String(255))
    failed_login_count = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    token_version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.SmallInteger, CheckConstraint('is_active IN (0,1)', name='chk_emp_is_active'), default=1)
    hired_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    sessions = db.relationship('UserSession', backref='employee')
    verifications = db.relationship('EmailVerification', backref='employee')
    orders = db.relationship('Order', backref='employee')

    @hybrid_property
    def role(self):
        if self.role_rel:
            name = self.role_rel.role_name.lower()
            if 'admin' in name:
                return 'admin'
            elif 'manager' in name:
                return 'manager'
            elif 'cashier' in name:
                return 'cashier'
            elif 'purchaser' in name or 'clerk' in name:
                return 'purchaser'
            elif 'kitchen' in name or 'staff' in name:
                return 'kitchen'
            return name
        return None

    @role.setter
    def role(self, value):
        if not value:
            self.role_id = None
            return
        # Find role by name
        role_rec = Role.query.filter(Role.role_name.ilike(f"%{value}%")).first()
        if not role_rec:
            # Fallbacks for legacy string values
            val_lower = value.lower()
            if 'admin' in val_lower:
                role_rec = Role.query.filter_by(role_name='Owner / Admin').first()
            elif 'manager' in val_lower:
                role_rec = Role.query.filter_by(role_name='Branch Manager').first()
            elif 'cashier' in val_lower:
                role_rec = Role.query.filter_by(role_name='Cashier').first()
            elif 'waiter' in val_lower:
                role_rec = Role.query.filter_by(role_name='Kitchen / Staff').first()
            elif 'purchaser' in val_lower or 'clerk' in val_lower:
                role_rec = Role.query.filter_by(role_name='Inventory Clerk / Purchaser').first()
            elif 'kitchen' in val_lower:
                role_rec = Role.query.filter_by(role_name='Kitchen / Staff').first()
        if role_rec:
            self.role_id = role_rec.role_id

    @role.expression
    def role(cls):
        return (
            select(
                db.case(
                    (Role.role_name.ilike('%admin%'), 'admin'),
                    (Role.role_name.ilike('%manager%'), 'manager'),
                    (Role.role_name.ilike('%cashier%'), 'cashier'),
                    (Role.role_name.ilike('%purchaser%'), 'purchaser'),
                    (Role.role_name.ilike('%clerk%'), 'purchaser'),
                    (Role.role_name.ilike('%kitchen%'), 'kitchen'),
                    (Role.role_name.ilike('%staff%'), 'kitchen'),
                    else_='kitchen'
                )
            )
            .where(Role.role_id == cls.role_id)
            .correlate_except(Role)
            .scalar_subquery()
        )

    def has_permission(self, module, action):
        if not self.role_rel:
            return False
        # Owner / Admin gets full access by default
        if self.role_rel.role_name == 'Owner / Admin':
            return True
        # Check permissions
        for perm in self.role_rel.permissions:
            if perm.module == module and perm.action == action:
                return True
        return False

    def get_id(self):
        return str(self.employee_id)

    def __repr__(self):
        return f'<Employee {self.email}>'
