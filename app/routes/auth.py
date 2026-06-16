from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from app.forms.auth_forms import LoginForm, ForgotPasswordForm, ResetPasswordForm
from app.services import auth_service

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        try:
            session = auth_service.login(form.email.data, form.password.data, request.remote_addr, request.user_agent.string)
            from app.models import Employee
            from extensions import db
            emp = db.session.get(Employee, session.employee_id)
            login_user(emp, remember=form.remember_me.data)
            return redirect(url_for('dashboard.dashboard'))
        except Exception as e:
            flash(str(e), 'error')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot', methods=['GET', 'POST'])
def forgot():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            auth_service.forgot_password(form.email.data)
            flash("Check your email", 'info')
        except Exception as e:
            flash(str(e), 'error')
    return render_template('auth/forgot.html', form=form)

@auth_bp.route('/reset', methods=['GET', 'POST'])
def reset():
    form = ResetPasswordForm(token=request.args.get('token'))
    if form.validate_on_submit():
        try:
            auth_service.reset_password(form.token.data, form.password.data)
            return redirect(url_for('auth.login'))
        except Exception as e:
            flash(str(e), 'error')
    return render_template('auth/reset.html', form=form)

@auth_bp.route('/verify/<token>', methods=['GET'])
def verify(token):
    try:
        auth_service.verify_email(token)
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('auth.login'))

@auth_bp.route('/verify-notice', methods=['GET'])
def verify_notice():
    return render_template('auth/verify_notice.html')
