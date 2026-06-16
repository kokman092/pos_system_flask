"""Menu Forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, BooleanField, TextAreaField, DecimalField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    display_order = IntegerField('Display Order', validators=[Optional(), NumberRange(min=0)])
    is_active = BooleanField('Is Active', default=True)

class MenuItemForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=150)])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()], validate_choice=False)
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    price = DecimalField('Price', places=2, validators=[DataRequired(), NumberRange(min=0)])
    tax_pct = DecimalField('Tax Percentage', places=2, validators=[Optional(), NumberRange(min=0, max=100)])
    is_available = BooleanField('Is Available', default=True)
    is_active = BooleanField('Is Active', default=True)

class ModifierForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    price = DecimalField('Price', places=2, validators=[Optional(), NumberRange(min=0)])
    group_name = StringField('Group Name', validators=[Optional(), Length(max=50)])
    is_active = BooleanField('Is Active', default=True)
