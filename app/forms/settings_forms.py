"""Settings Forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
import re

class PrinterConfigForm(FlaskForm):
    printer_role = SelectField('Printer Role', choices=[('kitchen', 'Kitchen'), ('receipt', 'Receipt'), ('bar', 'Bar')], validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    ip_address = StringField('IP Address', validators=[DataRequired(), Length(max=45)])
    port = IntegerField('Port', validators=[DataRequired(), NumberRange(min=1, max=65535)], default=9100)
    profile = SelectField('Profile', choices=[('epson', 'Epson'), ('star', 'Star'), ('generic', 'Generic')], default='epson', validators=[DataRequired()])
    is_enabled = BooleanField('Is Enabled', default=True)

    def validate_ip_address(self, field):
        pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
        if field.data and not re.match(pattern, field.data):
            raise ValidationError("Invalid IP address format.")

class BranchSettingsForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    location = StringField('Location', validators=[Optional(), Length(max=255)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    timezone = SelectField('Timezone', choices=[('Asia/Phnom_Penh', 'Asia/Phnom_Penh'), ('Asia/Bangkok', 'Asia/Bangkok'), ('Asia/Singapore', 'Asia/Singapore')], validators=[DataRequired()])
