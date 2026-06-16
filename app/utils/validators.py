"""
Validation utilities for AURA Restaurant POS.
Handles email, phone, password strength, and general data sanitization.
All functions are pure.
"""
import re

def is_valid_email(email: str) -> bool:
    """
    Checks if an email is in a valid RFC-compliant format.
    """
    if not email:
        return False
    # Simple RFC 5322 compliant regex
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))

def is_valid_phone(phone: str) -> bool:
    """
    Checks if a phone number is valid.
    Accepts +855, 0xx, and international formats.
    """
    if not phone:
        return False
    # Accepts optional '+', followed by digits and optional spaces/dashes
    pattern = r"^\+?[0-9\s\-]{8,20}$"
    return bool(re.match(pattern, phone))

def is_strong_password(password: str) -> tuple[bool, str]:
    """
    Checks if a password meets strength requirements.
    Rules: min 8 chars, 1 upper, 1 lower, 1 digit.
    Returns (True, "") if valid, else (False, "reason").
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    
    return True, ""

def is_valid_price(value) -> bool:
    """
    Checks if a value is a valid positive number (string or numeric).
    """
    try:
        val = float(value)
        return val >= 0
    except (ValueError, TypeError):
        return False

def is_valid_quantity(value) -> bool:
    """
    Checks if a value is a positive integer.
    """
    try:
        val = int(value)
        return val > 0 and float(value) == val
    except (ValueError, TypeError):
        return False

def sanitize_string(value: str, max_length: int = 255) -> str:
    """
    Sanitizes a string by stripping whitespace, truncating to max_length,
    and removing null bytes. Returns an empty string if value is None.
    """
    if not value:
        return ""
    
    sanitized = str(value).replace("\x00", "").strip()
    return sanitized[:max_length]
