"""Order Forms"""
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, TextAreaField, SelectField, DecimalField, FieldList
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

class CreateOrderForm(FlaskForm):
    table_id = IntegerField('Table ID', validators=[Optional()])
    order_type = SelectField('Order Type', choices=[('dine_in', 'Dine In'), ('takeaway', 'Takeaway'), ('delivery', 'Delivery')], validators=[DataRequired()])
    pax = IntegerField('Pax', validators=[Optional(), NumberRange(min=1, max=50)])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])

class AddItemForm(FlaskForm):
    item_id = IntegerField('Item ID', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1, max=99)])
    seat_number = IntegerField('Seat Number', validators=[Optional(), NumberRange(min=1, max=20)])
    notes = StringField('Notes', validators=[Optional(), Length(max=255)])
    modifier_ids = FieldList(IntegerField('Modifier ID'), validators=[Optional()])

class PaymentForm(FlaskForm):
    method = SelectField('Method', choices=[('cash', 'Cash'), ('card', 'Card'), ('qr_code', 'QR Code'), ('voucher', 'Voucher'), ('split', 'Split')], validators=[DataRequired()])
    amount = DecimalField('Amount', places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    tendered = DecimalField('Tendered', places=2, validators=[Optional(), NumberRange(min=0)])
    reference_no = StringField('Reference No', validators=[Optional(), Length(max=100)])
    customer_id = IntegerField('Customer ID', validators=[Optional()])
    points_to_redeem = IntegerField('Points to Redeem', validators=[Optional(), NumberRange(min=0)])

    def validate_tendered(self, field):
        if self.method.data == 'cash':
            if field.data is None:
                raise ValidationError("Tendered amount is required for cash payments.")
            if self.amount.data and field.data < self.amount.data:
                raise ValidationError("Tendered amount must be greater than or equal to the total amount.")

class CancelItemForm(FlaskForm):
    order_item_id = IntegerField('Order Item ID', validators=[DataRequired()])
    reason = StringField('Reason', validators=[DataRequired(), Length(min=3, max=255)])

class ApplyDiscountForm(FlaskForm):
    discount_type = SelectField('Discount Type', choices=[('fixed', 'Fixed'), ('percent', 'Percent')], validators=[DataRequired()])
    discount_value = DecimalField('Discount Value', places=2, validators=[DataRequired(), NumberRange(min=0)])

    def validate_discount_value(self, field):
        if self.discount_type.data == 'percent' and field.data > 100:
            raise ValidationError("Percent discount cannot exceed 100.")
