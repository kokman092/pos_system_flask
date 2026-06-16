"""Loyalty Service — handles customer lifecycle, points, and redemption.

award_points is idempotent: checks for existing LoyaltyTransaction
on the same order_id before creating a new one.
All DB-writing functions use explicit try/rollback.
"""
from extensions import db
from app.models import Customer, LoyaltyTransaction
from datetime import datetime


def get_or_create_customer(name: str, phone: str, email: str = None) -> Customer:
    """Gets an existing customer by phone/email or creates a new one."""
    if phone:
        customer = Customer.query.filter_by(phone=phone).first()
        if customer:
            return customer
    if email:
        customer = Customer.query.filter_by(email=email).first()
        if customer:
            return customer

    try:
        customer = Customer(name=name, phone=phone, email=email)
        db.session.add(customer)
        db.session.commit()
        return customer
    except Exception:
        db.session.rollback()
        raise


def search_customers(query: str, search_type: str = 'phone', branch_id: int = None) -> list:
    """Search customers by phone, email, or name."""
    q = f"%{query}%"
    base = Customer.query

    if search_type == 'phone':
        base = base.filter(Customer.phone.ilike(q))
    elif search_type == 'email':
        base = base.filter(Customer.email.ilike(q))
    else:
        base = base.filter(Customer.name.ilike(q))

    return base.limit(20).all()


def search_customers_paginated(query: str = None, search_type: str = 'phone', page: int = 1, per_page: int = 20) -> tuple:
    """Search customers with pagination. Returns (items, total)."""
    base = Customer.query

    if query:
        q = f"%{query}%"
        if search_type == 'phone':
            base = base.filter(Customer.phone.ilike(q))
        elif search_type == 'email':
            base = base.filter(Customer.email.ilike(q))
        else:
            base = base.filter(Customer.name.ilike(q))

    paginated = base.order_by(Customer.name).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return paginated.items, paginated.total


def award_points(customer_id: int, order_id: int, amount_paid_cents: int) -> LoyaltyTransaction:
    """Awards loyalty points to a customer based on amount paid.

    Idempotent: if points were already awarded for this order_id,
    returns the existing transaction instead of double-awarding.
    """
    customer = db.session.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    existing = LoyaltyTransaction.query.filter_by(
        customer_id=customer_id, order_id=order_id
    ).filter(LoyaltyTransaction.points_earned > 0).first()
    if existing:
        return existing

    points = amount_paid_cents // 100
    if points <= 0:
        return None

    try:
        tx = LoyaltyTransaction(
            customer_id=customer_id,
            order_id=order_id,
            points_earned=points,
            reason='Order Payment',
            points_balance_after=customer.points_balance + points
        )
        db.session.add(tx)

        customer.points_balance += points
        customer.total_spent_cents += amount_paid_cents
        db.session.commit()
        return tx
    except Exception:
        db.session.rollback()
        raise


def redeem_points(customer_id: int, order_id: int, points_to_redeem: int) -> tuple:
    """Redeems loyalty points for a discount or attaches customer if points is 0."""
    customer = db.session.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    from app.models import Order
    order = db.session.get(Order, order_id)
    if not order:
        raise ValueError("Order not found")

    if points_to_redeem < 0:
        raise ValueError("Points to redeem cannot be negative")

    if points_to_redeem == 0:
        try:
            order.customer_id = customer_id
            db.session.commit()
            from collections import namedtuple
            DummyTx = namedtuple('DummyTx', ['points_balance_after'])
            tx = DummyTx(points_balance_after=customer.points_balance)
            return tx, 0
        except Exception:
            db.session.rollback()
            raise

    if customer.points_balance < points_to_redeem:
        raise ValueError("Insufficient points balance")

    discount_cents = (points_to_redeem // 100) * 500

    try:
        tx = LoyaltyTransaction(
            customer_id=customer_id,
            order_id=order_id,
            points_redeemed=points_to_redeem,
            reason='Points Redemption',
            points_balance_after=customer.points_balance - points_to_redeem
        )
        db.session.add(tx)

        customer.points_balance -= points_to_redeem
        order.customer_id = customer_id
        order.discount_cents = (order.discount_cents or 0) + discount_cents
        db.session.commit()
        return tx, discount_cents
    except Exception:
        db.session.rollback()
        raise


def get_customer_summary(customer_id: int) -> dict:
    """Gets a summary of a customer's loyalty account. Read-only."""
    customer = db.session.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    transactions = (LoyaltyTransaction.query
                    .filter_by(customer_id=customer_id)
                    .order_by(LoyaltyTransaction.created_at.desc())
                    .limit(20)
                    .all())

    return {
        "customer_id": customer.customer_id,
        "name": customer.name,
        "phone": customer.phone,
        "email": customer.email,
        "points_balance": customer.points_balance,
        "total_spent_cents": customer.total_spent_cents,
        "tier": _get_tier(customer.total_spent_cents),
        "member_since": customer.created_at.strftime('%d %b %Y') if customer.created_at else '',
        "transactions": [
            {
                "type": t.transaction_type,
                "points": t.points_earned or t.points_redeemed,
                "balance_after": t.points_balance_after,
                "created_at": t.created_at.strftime('%d %b %Y %H:%M')
            }
            for t in transactions
        ]
    }


def _get_tier(total_spent_cents: int) -> dict:
    """Return tier name and next tier threshold."""
    tiers = [
        {"name": "Bronze",   "min": 0,       "color": "warning",  "icon": "🥉"},
        {"name": "Silver",   "min": 50000,    "color": "secondary","icon": "🥈"},
        {"name": "Gold",     "min": 200000,   "color": "warning",  "icon": "🥇"},
        {"name": "Platinum", "min": 500000,   "color": "info",     "icon": "💎"},
    ]
    current = tiers[0]
    next_tier = tiers[1]
    for i, tier in enumerate(tiers):
        if total_spent_cents >= tier["min"]:
            current = tier
            next_tier = tiers[i+1] if i+1 < len(tiers) else None
    return {
        "name": current["name"],
        "color": current["color"],
        "icon": current["icon"],
        "next": next_tier,
        "progress_pct": _tier_progress(total_spent_cents, current, next_tier)
    }


def _tier_progress(spent: int, current_tier: dict, next_tier: dict) -> int:
    if not next_tier:
        return 100
    range_ = next_tier["min"] - current_tier["min"]
    progress = spent - current_tier["min"]
    return min(int((progress / range_) * 100), 100)
