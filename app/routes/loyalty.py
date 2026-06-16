from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.forms.loyalty_forms import FindCustomerForm, CreateCustomerForm
from app.services import loyalty_service
from app.utils.response import success_response, error_response, not_found_response
from app.models import Order, Customer
from extensions import db

# Define blueprint without prefix to match root-level routing requirements
loyalty_bp = Blueprint('loyalty', __name__)


# GET /loyalty — main loyalty page
@loyalty_bp.route('/loyalty', methods=['GET'])
@login_required
def loyalty_page():
    form = FindCustomerForm()
    create_form = CreateCustomerForm()
    customers = []
    selected_customer = None

    search = request.args.get('search', '').strip()
    search_type = request.args.get('search_type', 'phone')
    customer_id = request.args.get('customer_id', type=int)

    if search:
        customers = loyalty_service.search_customers(
            query=search,
            search_type=search_type,
            branch_id=current_user.branch_id
        )
        if len(customers) == 1:
            selected_customer = loyalty_service.get_customer_summary(
                customers[0].customer_id
            )

    if customer_id:
        try:
            selected_customer = loyalty_service.get_customer_summary(customer_id)
        except ValueError:
            pass

    # Query open orders for this branch
    open_orders = Order.query.filter_by(
        branch_id=current_user.branch_id,
        status='open'
    ).order_by(Order.opened_at.desc()).all()

    recent_customers = Customer.query.order_by(Customer.created_at.desc()).limit(5).all()

    return render_template(
        'app/loyalty.html',
        form=form,
        create_form=create_form,
        customers=customers,
        selected_customer=selected_customer,
        search=search,
        search_type=search_type,
        open_orders=open_orders,
        recent_customers=recent_customers
    )


# GET /api/loyalty/search — live search JSON
@loyalty_bp.route('/api/loyalty/search', methods=['GET'])
@login_required
def search_customer():
    q = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'phone')
    page = request.args.get('page', 1, type=int)
    show_all = request.args.get('all', 'false').lower() == 'true'
    per_page = 20

    if not show_all and len(q) < 2:
        return success_response(data={"customers": [], "total": 0, "page": page, "has_more": False})

    customers, total = loyalty_service.search_customers_paginated(
        query=q if not show_all else None,
        search_type=search_type,
        page=page,
        per_page=per_page
    )
    return success_response(data={
        "customers": [c.to_dict() for c in customers],
        "total": total,
        "page": page,
        "has_more": (page * per_page) < total
    })


# GET /api/loyalty/<id> — get full customer summary
@loyalty_bp.route('/api/loyalty/<int:customer_id>', methods=['GET'])
@login_required
def get_customer(customer_id):
    try:
        summary = loyalty_service.get_customer_summary(customer_id)
        return success_response(data=summary)
    except ValueError as e:
        return not_found_response("Customer")


# POST /api/loyalty/customer — create customer
@loyalty_bp.route('/api/loyalty/customer', methods=['POST'])
@login_required
def create_customer():
    form = CreateCustomerForm()
    if form.validate_on_submit():
        try:
            customer = loyalty_service.get_or_create_customer(
                name=form.name.data,
                phone=form.phone.data,
                email=form.email.data or None
            )
            flash(f"Customer '{customer.name}' saved successfully.", "success")
            return redirect(url_for('loyalty.loyalty_page',
                                    search=customer.phone, search_type='phone', customer_id=customer.customer_id))
        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for('loyalty.loyalty_page'))


# POST /api/loyalty/redeem — redeem points or attach customer
@loyalty_bp.route('/api/loyalty/redeem', methods=['POST'])
@login_required
def redeem_points():
    try:
        customer_id = int(request.json.get('customer_id'))
        order_id = int(request.json.get('order_id'))
        points = int(request.json.get('points_to_redeem', 0))
        transaction, discount_cents = loyalty_service.redeem_points(
            customer_id=customer_id,
            order_id=order_id,
            points_to_redeem=points
        )
        return success_response(data={
            "discount_cents": discount_cents,
            "new_balance": transaction.points_balance_after,
            "message": f"Redeemed {points} points for {discount_cents / 100:.2f} discount" if points > 0 else "Customer attached to order successfully"
        })
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        db.session.rollback()
        return error_response("Redemption failed", 500)
