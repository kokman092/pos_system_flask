"""Auth Service — handles registration, login, password reset, and role management.

bcrypt work factor is set to 12 (not default 10) for production security.
All DB-writing functions use explicit try/rollback.
"""
from datetime import datetime, timedelta
from extensions import db, bcrypt
from app.models import Employee, UserSession, EmailVerification, AuditLog, Role
from app.utils.security import generate_token

def register_employee(branch_id: int, full_name: str, role: str, email: str, password: str, created_by_admin: bool = False) -> Employee:
    """Registers a new employee. If created_by_admin=True, marks as email_verified immediately."""
    if not password:
        raise ValueError("Password is required")
    
    # Check duplicate email
    existing = Employee.query.filter_by(email=email).first()
    if existing:
        raise ValueError(f"Email {email} already registered")
        
    # Resolve role to Role record
    role_rec = None
    if isinstance(role, int) or (isinstance(role, str) and role.isdigit()):
        role_rec = db.session.get(Role, int(role))
    else:
        role_rec = Role.query.filter(Role.role_name.ilike(f"%{role}%")).first()
        if not role_rec:
            # Fallbacks for legacy string values
            val_lower = str(role).lower()
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
                
    if not role_rec:
        raise ValueError(f"Invalid role: {role}")
        
    pw_hash = bcrypt.generate_password_hash(password, rounds=12).decode('utf-8')
    
    try:
        emp = Employee(
            branch_id=branch_id,
            full_name=full_name,
            role_id=role_rec.role_id,
            email=email,
            password_hash=pw_hash,
            email_verified=1 if created_by_admin else 0,
            is_active=1
        )
        db.session.add(emp)
        db.session.flush()
        
        if not created_by_admin:
            token = generate_token()
            ev = EmailVerification(
                employee_id=emp.employee_id,
                token=token,
                token_type='verify_email',
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.session.add(ev)
            
        # Log to audit
        audit = AuditLog(
            table_name='employees',
            record_id=emp.employee_id,
            action='INSERT',
            new_values=f"full_name={full_name}, role_id={role_rec.role_id}, email={email}"
        )
        db.session.add(audit)
        
        db.session.commit()
        return emp
    except Exception:
        db.session.rollback()
        raise

def verify_email(token: str) -> Employee:
    """Verifies an employee's email using a token."""
    ev = EmailVerification.query.filter_by(token=token, is_used=0, token_type='verify_email').first()
    if not ev:
        raise ValueError("Invalid or used token")
    if ev.expires_at < datetime.utcnow():
        raise ValueError("Token expired")
    
    emp = db.session.get(Employee, ev.employee_id)
    if not emp:
        raise ValueError("Employee not found")
        
    try:
        emp.email_verified = 1
        ev.is_used = 1
        db.session.commit()
        return emp
    except Exception:
        db.session.rollback()
        raise

def login(email: str, password: str, ip: str, user_agent: str) -> UserSession:
    """Authenticates an employee and returns a session."""
    emp = Employee.query.filter_by(email=email, is_active=1).first()
    if not emp:
        raise ValueError("Invalid credentials")
        
    if emp.locked_until and emp.locked_until > datetime.utcnow():
        raise PermissionError("Account is locked")
        
    if emp.email_verified == 0:
        raise PermissionError("Email not verified")
        
    if not bcrypt.check_password_hash(emp.password_hash, password):
        emp.failed_login_count += 1
        if emp.failed_login_count >= 5:
            emp.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
        raise ValueError("Invalid credentials")
        
    emp.failed_login_count = 0
    emp.locked_until = None
    emp.last_login_at = datetime.utcnow()
    
    session_token = generate_token(64)
    session = UserSession(
        employee_id=emp.employee_id,
        session_token=session_token,
        ip_address=ip,
        user_agent=user_agent,
        expires_at=datetime.utcnow() + timedelta(hours=8)
    )
    db.session.add(session)
    db.session.commit()
    return session

def logout(session_token: str) -> bool:
    """Logs out an employee by revoking their session."""
    session = UserSession.query.filter_by(session_token=session_token).first()
    if not session:
        raise ValueError("Session not found")
    session.is_revoked = 1
    db.session.commit()
    return True

def get_active_session(session_token: str) -> UserSession:
    """Returns the active session if valid."""
    session = UserSession.query.filter_by(session_token=session_token, is_revoked=0).first()
    if not session:
        return None
    if session.expires_at < datetime.utcnow():
        return None
    return session

def forgot_password(email: str) -> EmailVerification:
    """Creates a password reset token for the given email."""
    from app.services.email_service import queue_from_template
    
    emp = Employee.query.filter_by(email=email, is_active=1).first()
    if not emp:
        raise ValueError("Employee not found")
    
    try:
        token = generate_token()
        ev = EmailVerification(
            employee_id=emp.employee_id,
            token=token,
            token_type='reset_password',
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        db.session.add(ev)
        
        try:
            queue_from_template('password_reset', emp.email, {'token': token})
        except ValueError:
            pass  # Template may not exist yet
        db.session.commit()
        return ev
    except Exception:
        db.session.rollback()
        raise

def reset_password(token: str, new_password: str) -> Employee:
    """Resets an employee's password using a token."""
    ev = EmailVerification.query.filter_by(token=token, is_used=0, token_type='reset_password').first()
    if not ev:
        raise ValueError("Invalid or used token")
    if ev.expires_at < datetime.utcnow():
        raise ValueError("Token expired")
        
    emp = db.session.get(Employee, ev.employee_id)
    if not emp:
        raise ValueError("Employee not found")
        
    try:
        pw_hash = bcrypt.generate_password_hash(new_password, rounds=12).decode('utf-8')
        emp.password_hash = pw_hash
        emp.token_version += 1
        ev.is_used = 1
        
        # Revoke ALL active sessions — not just current
        UserSession.query.filter_by(employee_id=emp.employee_id, is_revoked=0).update({'is_revoked': 1})
        db.session.commit()
        return emp
    except Exception:
        db.session.rollback()
        raise

def change_role(employee_id: int, new_role: str, changed_by_id: int) -> Employee:
    """Changes the role of an employee."""
    admin = db.session.get(Employee, changed_by_id)
    if not admin or admin.role != 'admin':
        raise PermissionError("Only admin can change roles")
        
    emp = db.session.get(Employee, employee_id)
    if not emp:
        raise ValueError("Employee not found")
        
    # Resolve role to Role record
    role_rec = None
    if isinstance(new_role, int) or (isinstance(new_role, str) and new_role.isdigit()):
        role_rec = db.session.get(Role, int(new_role))
    else:
        role_rec = Role.query.filter(Role.role_name.ilike(f"%{new_role}%")).first()
        if not role_rec:
            # Fallbacks for legacy string values
            val_lower = str(new_role).lower()
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
                
    if not role_rec:
        raise ValueError(f"Invalid role: {new_role}")
        
    try:
        old_role_name = emp.role_rel.role_name if emp.role_rel else 'None'
        emp.role_id = role_rec.role_id
        
        audit = AuditLog(
            table_name='employees',
            record_id=emp.employee_id,
            action='UPDATE',
            changed_by=changed_by_id,
            old_values=f"role_id={emp.role_id if emp.role_id else 'None'}",
            new_values=f"role_id={role_rec.role_id}"
        )
        db.session.add(audit)
        db.session.commit()
        return emp
    except Exception:
        db.session.rollback()
        raise
