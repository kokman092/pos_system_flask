"""Inventory Forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, SelectField, FieldList, FormField, HiddenField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class AddStockBatchForm(FlaskForm):
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()], validate_choice=False)
    qty_received = DecimalField('Quantity Received', places=3, validators=[DataRequired(), NumberRange(min=0.001)])
    cost_per_unit = DecimalField('Cost Per Unit', places=2, validators=[DataRequired(), NumberRange(min=0)])
    expiry_date = DateField('Expiry Date', validators=[Optional()])
    supplier_ref = StringField('Supplier Reference', validators=[Optional(), Length(max=100)])

class WasteLogForm(FlaskForm):
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()], validate_choice=False)
    qty = DecimalField('Quantity', places=3, validators=[DataRequired(), NumberRange(min=0.001)])
    reason = StringField('Reason', validators=[DataRequired(), Length(min=3, max=255)])

class AdjustStockForm(FlaskForm):
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()], validate_choice=False)
    adjustment_type = SelectField('Adjustment Type', choices=[('set', 'Set'), ('add', 'Add'), ('remove', 'Remove')], default='set', validators=[DataRequired()])
    set_qty = DecimalField('Quantity', places=3, validators=[DataRequired(), NumberRange(min=0)])
    reason = StringField('Reason', validators=[DataRequired(), Length(min=3, max=255)])

class InventoryCountForm(FlaskForm):
    session_name = StringField('Session Name', validators=[DataRequired(), Length(max=100)])

class CountItemForm(FlaskForm):
    ingredient_id = HiddenField('Ingredient ID', validators=[DataRequired()])
    counted_qty = DecimalField('Counted Quantity', places=3, validators=[DataRequired(), NumberRange(min=0)])

class SubmitCountForm(FlaskForm):
    counts = FieldList(FormField(CountItemForm), min_entries=1)


class SupplierForm(FlaskForm):
    name = StringField('Supplier Name', validators=[DataRequired(), Length(max=100)])
    contact_name = StringField('Contact Name', validators=[Optional(), Length(max=100)])
    phone = StringField('Phone', validators=[Optional(), Length(max=30)])
    email = StringField('Email', validators=[Optional(), Length(max=100)])
    address = StringField('Address', validators=[Optional(), Length(max=255)])
    image_path = StringField('Image URL/Path', validators=[Optional(), Length(max=255)])
    notes = StringField('Notes', validators=[Optional(), Length(max=500)])
    is_preferred = SelectField('Preferred Supplier', coerce=int, choices=[(0, 'No'), (1, 'Yes')], default=0, validators=[Optional()])
    is_active = SelectField('Status', coerce=int, choices=[(1, 'Active'), (0, 'Inactive')], default=1, validators=[Optional()])


class PurchaseOrderItemForm(FlaskForm):
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()], validate_choice=False)
    ordered_qty = DecimalField('Ordered Qty', places=3, validators=[DataRequired(), NumberRange(min=0.001)])
    unit_cost = DecimalField('Unit Cost', places=2, validators=[DataRequired(), NumberRange(min=0)])


class PurchaseOrderForm(FlaskForm):
    supplier_id = SelectField('Supplier', coerce=int, validators=[DataRequired()], validate_choice=False)
    expected_at = DateField('Expected Delivery Date', validators=[Optional()])
    notes = StringField('Notes', validators=[Optional(), Length(max=500)])
    items = FieldList(FormField(PurchaseOrderItemForm), min_entries=1)


class ReceivePurchaseOrderItemForm(FlaskForm):
    purchase_order_item_id = HiddenField('PO Item ID', validators=[DataRequired()])
    received_qty = DecimalField('Received Qty', places=3, validators=[DataRequired(), NumberRange(min=0)])
    actual_unit_cost = DecimalField('Actual Unit Cost', places=2, validators=[DataRequired(), NumberRange(min=0)])
    expiry_date = DateField('Expiry Date', validators=[Optional()])
    supplier_ref = StringField('Supplier Ref', validators=[Optional(), Length(max=100)])


class ReceivePurchaseOrderForm(FlaskForm):
    invoice_ref = StringField('Invoice Ref/Supplier Invoice No.', validators=[Optional(), Length(max=100)])
    received_items = FieldList(FormField(ReceivePurchaseOrderItemForm))


class IngredientForm(FlaskForm):
    name = StringField('Ingredient Name', validators=[DataRequired(), Length(max=100)])
    unit = StringField('Unit (e.g. kg, pcs, liters)', validators=[DataRequired(), Length(max=20)])
    reorder_level = DecimalField('Low Stock Alert Level', places=3, validators=[DataRequired(), NumberRange(min=0)])
    default_supplier_id = SelectField('Default Supplier (Optional)', coerce=int, validators=[Optional()], validate_choice=False)
    current_qty = DecimalField('Current Stock (Optional)', places=3, validators=[Optional(), NumberRange(min=0)])
    is_active = SelectField('Status', coerce=int, choices=[(1, 'Active'), (0, 'Inactive')], default=1, validators=[Optional()])
    image_path = StringField('Image URL/Path', validators=[Optional(), Length(max=255)])
