"""Reservation Forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, IntegerField, SelectField, TextAreaField, DateTimeLocalField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError
from datetime import datetime
from app.utils.validators import is_valid_phone

class ReservationForm(FlaskForm):
    customer_name = StringField('Customer Name', validators=[DataRequired(), Length(max=100)])
    customer_email = EmailField('Customer Email', validators=[Optional(), Email()])
    customer_phone = StringField('Customer Phone', validators=[Optional(), Length(max=20)])
    party_size = IntegerField('Party Size', validators=[DataRequired(), NumberRange(min=1, max=30)])
    table_id = SelectField('Table', coerce=int, validators=[Optional()], validate_choice=False)
    reserved_at = DateTimeLocalField('Reserved At', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])

    def validate_customer_phone(self, field):
        if field.data and not is_valid_phone(field.data):
            raise ValidationError("Invalid phone number format.")

    def validate_reserved_at(self, field):
        if field.data and field.data < datetime.now():
            raise ValidationError("Reservation time must be in the future.")

class UpdateReservationStatusForm(FlaskForm):
    reservation_id = IntegerField('Reservation ID', validators=[DataRequired()])
    status = SelectField('Status', choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('seated', 'Seated'), ('cancelled', 'Cancelled'), ('no_show', 'No Show')], validators=[DataRequired()])
