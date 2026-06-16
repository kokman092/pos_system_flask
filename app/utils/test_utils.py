import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from flask import Flask
from app.utils.money import *
from app.utils.security import *
from app.utils.validators import *
from app.utils.pagination import *
from app.utils.datetime_helpers import *
from app.utils.response import *

# --- money.py ---
def test_cents_to_display():
    assert cents_to_display(10050) == "100.50"
    assert cents_to_display(0) == "0.00"
    assert cents_to_display(None) == "0.00"

def test_display_to_cents():
    assert display_to_cents("100.50") == 10050
    assert display_to_cents("100") == 10000
    assert display_to_cents(100.5) == 10050
    assert display_to_cents(None) == 0
    assert display_to_cents("invalid") == 0

def test_format_currency():
    assert format_currency(10050) == "$100.50"
    assert format_currency(0, symbol="€") == "€0.00"

def test_cents_to_float():
    assert cents_to_float(10050) == 100.50
    assert cents_to_float(0) == 0.0
    assert cents_to_float(None) == 0.0

def test_calculate_tax():
    assert calculate_tax(10000, 5.5) == 550
    assert calculate_tax(10050, 10.0) == 1005
    assert calculate_tax(0, 5.5) == 0

def test_calculate_total():
    assert calculate_total(10000, 5.0, 0) == 10500
    assert calculate_total(10000, 5.0, 1000) == 9500
    assert calculate_total(1000, 10.0, 2000) == 0  # Discount larger than total

# --- security.py ---
def test_generate_token():
    token1 = generate_token()
    token2 = generate_token(16)
    assert len(token1) > 0
    assert token1 != token2

def test_generate_uuid():
    uuid1 = generate_uuid()
    uuid2 = generate_uuid()
    assert len(uuid1) == 36
    assert uuid1 != uuid2

def test_hash_pin():
    hash1 = hash_pin("1234")
    hash2 = hash_pin("4321")
    assert len(hash1) == 64
    assert hash1 != hash2
    assert hash_pin(None) == ""

def test_safe_str_compare():
    assert safe_str_compare("abc", "abc") == True
    assert safe_str_compare("abc", "abd") == False
    assert safe_str_compare(None, "abc") == False

def test_token_expiry():
    exp1 = token_expiry(60)
    exp2 = token_expiry(0)
    now = datetime.utcnow()
    assert exp1 > now
    assert exp2 <= now + timedelta(seconds=1)

def test_is_token_expired():
    future = datetime.utcnow() + timedelta(minutes=10)
    past = datetime.utcnow() - timedelta(minutes=10)
    assert is_token_expired(future) == False
    assert is_token_expired(past) == True
    assert is_token_expired(None) == True

# --- validators.py ---
def test_is_valid_email():
    assert is_valid_email("test@example.com") == True
    assert is_valid_email("invalid-email") == False
    assert is_valid_email(None) == False

def test_is_valid_phone():
    assert is_valid_phone("+85512345678") == True
    assert is_valid_phone("012345678") == True
    assert is_valid_phone("invalid") == False

def test_is_strong_password():
    valid, msg = is_strong_password("StrongPass1!")
    assert valid == True
    valid, msg = is_strong_password("weak")
    assert valid == False
    assert "least 8" in msg
    valid, msg = is_strong_password("onlylowercase1!")
    assert valid == False

def test_is_valid_price():
    assert is_valid_price("10.5") == True
    assert is_valid_price(-5) == False
    assert is_valid_price("abc") == False

def test_is_valid_quantity():
    assert is_valid_quantity("5") == True
    assert is_valid_quantity("5.5") == False
    assert is_valid_quantity(-2) == False
    assert is_valid_quantity("abc") == False

def test_sanitize_string():
    assert sanitize_string("  hello \x00 world  ") == "hello  world"
    assert sanitize_string("a" * 300, max_length=10) == "a" * 10
    assert sanitize_string(None) == ""

# --- datetime_helpers.py ---
def test_now_local():
    dt = now_local()
    assert dt is not None
    assert dt.tzinfo is not None

def test_utc_to_local():
    utc_dt = datetime(2026, 6, 10, 12, 0, 0)
    local_dt = utc_to_local(utc_dt)
    assert local_dt.hour != 12  # Assuming local timezone is not UTC
    assert utc_to_local(None) is None

def test_format_datetime():
    dt = datetime(2026, 6, 10, 15, 30)
    assert format_datetime(dt) == "10 Jun 2026 15:30"
    assert format_datetime(None) == ""

def test_format_date():
    dt = datetime(2026, 6, 10, 15, 30)
    assert format_date(dt) == "10 Jun 2026"
    assert format_date(None) == ""

def test_format_time():
    dt = datetime(2026, 6, 10, 15, 30)
    assert format_time(dt) == "15:30"
    assert format_time(None) == ""

def test_minutes_since():
    past = datetime.utcnow() - timedelta(minutes=5, seconds=30)
    assert minutes_since(past) == 5
    assert minutes_since(None) == 0

def test_start_of_day():
    dt = datetime(2026, 6, 10, 15, 30)
    sod = start_of_day(dt)
    assert sod.hour == 0 and sod.minute == 0

def test_end_of_day():
    dt = datetime(2026, 6, 10, 15, 30)
    eod = end_of_day(dt)
    assert eod.hour == 23 and eod.minute == 59

def test_shift_start_end():
    start, end = shift_start_end("morning")
    assert start.hour == 6 and end.hour == 14
    start, end = shift_start_end("night")
    assert start.hour == 22 and end.hour == 6

# --- pagination.py ---
def test_paginate_query():
    mock_query = MagicMock()
    mock_paginated = MagicMock()
    mock_paginated.items = [1, 2, 3]
    mock_paginated.total = 3
    mock_paginated.pages = 1
    mock_paginated.page = 1
    mock_paginated.has_next = False
    mock_paginated.has_prev = False
    mock_query.paginate.return_value = mock_paginated

    res = paginate_query(mock_query, 1, 20)
    assert res["total"] == 3
    assert res["items"] == [1, 2, 3]

def test_get_page_from_request():
    mock_req = MagicMock()
    mock_req.args.get.return_value = 2
    assert get_page_from_request(mock_req) == 2
    
    mock_req.args.get.side_effect = Exception("error")
    assert get_page_from_request(mock_req, default=5) == 5

# --- response.py ---
def test_success_response():
    app = Flask(__name__)
    with app.app_context():
        resp, status = success_response({"id": 1}, "Created")
        assert status == 200
        assert resp.json["message"] == "Created"
        assert resp.json["data"] == {"id": 1}

def test_error_response():
    app = Flask(__name__)
    with app.app_context():
        resp, status = error_response("Bad", 400, {"field": "required"})
        assert status == 400
        assert resp.json["message"] == "Bad"
        assert resp.json["errors"] == {"field": "required"}

def test_not_found_response():
    app = Flask(__name__)
    with app.app_context():
        resp, status = not_found_response("User")
        assert status == 404
        assert resp.json["message"] == "User not found"

def test_unauthorized_response():
    app = Flask(__name__)
    with app.app_context():
        resp, status = unauthorized_response()
        assert status == 401
        assert resp.json["message"] == "Unauthorized"

def test_validation_error_response():
    app = Flask(__name__)
    with app.app_context():
        resp, status = validation_error_response({"email": "invalid"})
        assert status == 422
        assert resp.json["message"] == "Validation failed"
        assert resp.json["errors"]["email"] == "invalid"
