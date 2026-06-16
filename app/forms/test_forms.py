"""Test Forms"""
import pytest
from datetime import datetime, timedelta
from flask import Flask
from werkzeug.datastructures import MultiDict
from app.forms import LoginForm, ResetPasswordForm, PaymentForm, ReservationForm, CreateCustomerForm

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['WTF_CSRF_ENABLED'] = False
    return app

def test_login_form_valid(app):
    with app.test_request_context():
        form = LoginForm(MultiDict({'email': 'test@example.com', 'password': 'password123'}))
        assert form.validate() is True

def test_login_form_missing_required(app):
    with app.test_request_context():
        form = LoginForm(MultiDict({'email': 'test@example.com'}))
        assert form.validate() is False
        assert 'password' in form.errors

def test_login_form_invalid_email(app):
    with app.test_request_context():
        form = LoginForm(MultiDict({'email': 'invalid-email', 'password': 'password123'}))
        assert form.validate() is False
        assert 'email' in form.errors

def test_reset_password_weak(app):
    with app.test_request_context():
        form = ResetPasswordForm(MultiDict({
            'token': 'abc',
            'password': 'weakpassword',
            'confirm_password': 'weakpassword'
        }))
        assert form.validate() is False
        assert 'password' in form.errors
        assert "Password must contain at least one uppercase letter." in form.errors['password'][0]

def test_payment_form_tendered_less_than_amount(app):
    with app.test_request_context():
        form = PaymentForm(MultiDict({
            'method': 'cash',
            'amount': '10.00',
            'tendered': '5.00'
        }))
        assert form.validate() is False
        assert 'tendered' in form.errors
        assert "Tendered amount must be greater than or equal to the total amount" in form.errors['tendered'][0]

def test_reservation_form_past_datetime(app):
    with app.test_request_context():
        past_dt = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        form = ReservationForm(MultiDict({
            'customer_name': 'John Doe',
            'party_size': '2',
            'reserved_at': past_dt
        }))
        assert form.validate() is False
        assert 'reserved_at' in form.errors
        assert "Reservation time must be in the future." in form.errors['reserved_at'][0]

def test_create_customer_invalid_phone(app):
    with app.test_request_context():
        form = CreateCustomerForm(MultiDict({
            'name': 'John',
            'phone': 'invalid_phone'
        }))
        assert form.validate() is False
        assert 'phone' in form.errors
        assert "Invalid phone number format." in form.errors['phone'][0]

def test_create_customer_valid_phone(app):
    with app.test_request_context():
        form = CreateCustomerForm(MultiDict({
            'name': 'John',
            'phone': '+85512345678'
        }))
        assert form.validate() is True
