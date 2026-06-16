"""
Money utilities for AURA Restaurant POS.
Handles conversion between cents (storage) and display formats (strings, floats).
All functions are pure.
"""

def cents_to_display(cents: int) -> str:
    """
    Converts cents to a display string with 2 decimal places.
    Example: 10050 -> '100.50', 0 -> '0.00'
    """
    if cents is None:
        return "0.00"
    return f"{cents / 100:.2f}"

def display_to_cents(value: str | float | int) -> int:
    """
    Converts a display string, float, or int to integer cents.
    Example: '100.50' -> 10050, 100 -> 10000
    """
    if value is None or value == "":
        return 0
    try:
        # Convert to float first, then multiply by 100 and round to avoid floating point issues
        return int(round(float(value) * 100))
    except ValueError:
        return 0

def format_currency(cents: int, symbol: str = "$") -> str:
    """
    Formats cents as a currency string.
    Example: 10050 -> '$100.50'
    """
    return f"{symbol}{cents_to_display(cents)}"

def cents_to_float(cents: int) -> float:
    """
    Converts cents to a float representation.
    Example: 10050 -> 100.50
    """
    if cents is None:
        return 0.0
    return float(cents) / 100.0

def calculate_tax(price_cents: int, tax_pct: float) -> int:
    """
    Calculates the tax amount in cents based on the price and tax percentage.
    Rounds to the nearest cent.
    Example: calculate_tax(10000, 5.5) -> 550
    """
    if not price_cents or not tax_pct:
        return 0
    return int(round(price_cents * (tax_pct / 100.0)))

def calculate_total(price_cents: int, tax_pct: float, discount_cents: int = 0) -> int:
    """
    Calculates the final total in cents (price + tax - discount).
    """
    tax = calculate_tax(price_cents, tax_pct)
    total = price_cents + tax - discount_cents
    return max(0, total)
