"""Loyalty Forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, EmailField
from wtforms.validators import DataRequired, Length, Email, Optional, ValidationError
from app.utils.validators import is_valid_phone

class FindCustomerForm(FlaskForm):
    search = StringField('Search', validators=[DataRequired(), Length(min=3)])
    search_type = SelectField('Search Type', choices=[('phone', 'Phone'), ('email', 'Email'), ('name', 'Name')], validators=[DataRequired()])

class CreateCustomerForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)])
    email = EmailField('Email', validators=[Optional(), Email()])

    def validate_phone(self, field):
        if field.data and not is_valid_phone(field.data):
            raise ValidationError("Invalid phone number format.")
