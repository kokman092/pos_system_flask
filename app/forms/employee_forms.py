"""Employee Forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SelectField, BooleanField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.utils.validators import is_strong_password

class InviteEmployeeForm(FlaskForm):
    full_name = StringField('Full Name', validators=[
        DataRequired(), Length(max=100)
    ])
    email = EmailField('Email Address', validators=[
        DataRequired(), Email(), Length(max=255)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, max=128)
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match')
    ])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()], validate_choice=False)
    branch_id = SelectField('Branch', coerce=int, validators=[DataRequired()])

    def validate_password(self, field):
        valid, reason = is_strong_password(field.data)
        if not valid:
            raise ValidationError(reason)

    def validate_email(self, field):
        from app.models import Employee
        existing = Employee.query.filter_by(email=field.data).first()
        if existing:
            raise ValidationError('Email already registered.')

class EditEmployeeForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()], validate_choice=False)
    is_active = BooleanField('Is Active')

class ChangeRoleForm(FlaskForm):
    employee_id = IntegerField('Employee ID', validators=[DataRequired()])
    new_role_id = SelectField('New Role', coerce=int, validators=[DataRequired()], validate_choice=False)
