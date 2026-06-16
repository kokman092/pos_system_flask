from functools import wraps
from flask import jsonify, redirect, url_for, flash, request, render_template
from flask_login import current_user
from app.utils.response import error_response

def permission_required(module, action):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.headers.get('Accept') == 'application/json':
                    return error_response("Unauthorized", 401)
                return redirect(url_for('auth.login'))
            if not current_user.has_permission(module, action):
                if request.is_json or request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                    return error_response("Forbidden: Insufficient Permissions", 403)
                return render_template('errors/403.html'), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.headers.get('Accept') == 'application/json':
                    return error_response("Unauthorized", 401)
                return redirect(url_for('auth.login'))
            
            user_role = current_user.role
            effective_roles = {user_role}
            if user_role == 'kitchen':
                effective_roles.add('waiter')
            elif user_role == 'waiter':
                effective_roles.add('kitchen')
                
            if not any(r in roles for r in effective_roles):
                if request.is_json or request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                    return error_response("Forbidden", 403)
                return render_template('errors/403.html'), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def branch_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.branch_id:
            return error_response("Branch isolation required", 403)
        return f(*args, **kwargs)
    return decorated_function

def verified_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.email_verified != 1:
            return redirect(url_for('auth.verify_notice'))
        return f(*args, **kwargs)
    return decorated_function
