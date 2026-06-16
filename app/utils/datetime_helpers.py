"""
Datetime utilities for AURA Restaurant POS.
Handles timezone conversions and formatting.
All functions are pure except when relying on current system time.
"""
from datetime import datetime, timedelta
import pytz

TIMEZONE = "Asia/Phnom_Penh"

def get_tz():
    return pytz.timezone(TIMEZONE)

def now_local() -> datetime:
    """
    Returns the current time in the local timezone.
    """
    return datetime.now(get_tz())

def utc_to_local(dt: datetime) -> datetime:
    """
    Converts a UTC datetime to the local timezone.
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(get_tz())

def format_datetime(dt: datetime, fmt: str = "%d %b %Y %H:%M") -> str:
    """
    Formats a datetime object to a human-readable string.
    """
    if not dt:
        return ""
    return dt.strftime(fmt)

def format_date(dt: datetime) -> str:
    """
    Formats a datetime object to "10 Jun 2026".
    """
    if not dt:
        return ""
    return dt.strftime("%d %b %Y")

def format_time(dt: datetime) -> str:
    """
    Formats a datetime object to "22:14".
    """
    if not dt:
        return ""
    return dt.strftime("%H:%M")

def minutes_since(dt: datetime) -> int:
    """
    Returns how many minutes ago a datetime was compared to UTC now.
    Assumes dt is naive and in UTC, matching default SQLAlchemy times.
    """
    if not dt:
        return 0
    now = datetime.utcnow()
    diff = now - dt
    return int(diff.total_seconds() / 60)

def start_of_day(dt: datetime = None) -> datetime:
    """
    Returns midnight of the given date (or today in local tz).
    """
    if dt is None:
        dt = now_local()
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def end_of_day(dt: datetime = None) -> datetime:
    """
    Returns 23:59:59 of the given date (or today in local tz).
    """
    if dt is None:
        dt = now_local()
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)

def shift_start_end(shift: str = "morning") -> tuple[datetime, datetime]:
    """
    Returns the start and end datetime for a specific shift today.
    "morning" -> 06:00-14:00
    "afternoon" -> 14:00-22:00
    "night" -> 22:00-06:00
    """
    base = start_of_day()
    shift = shift.lower()
    
    if shift == "afternoon":
        return base.replace(hour=14), base.replace(hour=22)
    elif shift == "night":
        start = base.replace(hour=22)
        end = (base + timedelta(days=1)).replace(hour=6)
        return start, end
    else:  # morning default
        return base.replace(hour=6), base.replace(hour=14)
