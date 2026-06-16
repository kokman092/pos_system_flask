"""Authentication Forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, HiddenField, EmailField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.utils.validators import is_strong_password

class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=128)])
    remember_me = BooleanField('Remember Me')

class ForgotPasswordForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])

class ResetPasswordForm(FlaskForm):
    token = HiddenField('Token', validators=[DataRequired()])
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])

    def validate_password(self, field):
        is_strong, msg = is_strong_password(field.data)
        if not is_strong:
            raise ValidationError(msg)

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_password', message='Passwords must match')])

    def validate_new_password(self, field):
        is_strong, msg = is_strong_password(field.data)
        if not is_strong:
            raise ValidationError(msg)

    
