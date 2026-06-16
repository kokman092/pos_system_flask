"""
Security utilities for AURA Restaurant POS.
Handles token generation, hashing, and token expiry.
All functions are pure except for randomness functions.
"""
import secrets
import hashlib
import uuid
from datetime import datetime, timedelta

def generate_token(length: int = 32) -> str:
    """
    Generates a URL-safe random token.
    Default length is 32 bytes (which results in a ~43 character string).
    """
    return secrets.token_urlsafe(length)

def generate_uuid() -> str:
    """
    Generates a UUID4 string for offline sync client IDs and other UUID needs.
    """
    return str(uuid.uuid4())

def hash_pin(pin: str) -> str:
    """
    Generates a SHA256 hash for a POS PIN.
    Fast hash designed for terminal use.
    """
    if not pin:
        return ""
    return hashlib.sha256(pin.encode('utf-8')).hexdigest()

def safe_str_compare(a: str, b: str) -> bool:
    """
    Performs a constant-time string comparison to prevent timing attacks.
    """
    if a is None or b is None:
        return False
    return secrets.compare_digest(a, b)

def token_expiry(minutes: int) -> datetime:
    """
    Returns a datetime object representing UTC now + the specified minutes.
    """
    return datetime.utcnow() + timedelta(minutes=minutes)

def is_token_expired(expiry: datetime) -> bool:
    """
    Checks if a token's expiry datetime has passed based on current UTC time.
    """
    if not expiry:
        return True
    return expiry < datetime.utcnow()
