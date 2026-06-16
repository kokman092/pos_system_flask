from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.forms.reservation_forms import ReservationForm
from app.models import Reservation, RestaurantTable
from app.utils.response import success_response
from extensions import db
from datetime import datetime

reservations_bp = Blueprint('reservations', __name__, url_prefix='/reservations')


@reservations_bp.route('', methods=['GET', 'POST'])
@login_required
def index():
    """Reservations page — lists reservations and handles creation."""
    form = ReservationForm()
    tables = RestaurantTable.query.filter_by(
        branch_id=current_user.branch_id
    ).order_by(RestaurantTable.table_number).all()

    # Populate table choices for the form
    form.table_id.choices = [(0, '-- Auto Assign --')] + [
        (t.table_id, f'{t.table_number} (seats {t.capacity})')
        for t in tables
    ]

    if request.method == 'POST' and form.validate_on_submit():
        table_id = form.table_id.data if form.table_id.data else None
        reserved_at = form.reserved_at.data
        branch_id = current_user.branch_id

        if table_id and table_id != 0:
            existing = Reservation.query.filter(
                Reservation.table_id == table_id,
                Reservation.reserved_at == reserved_at,
                Reservation.branch_id == branch_id,
                Reservation.status != 'cancelled'
            ).first()
            if existing:
                flash('A reservation already exists for this table at the selected time.', 'warning')
                return redirect(url_for('reservations.index'))

        try:
            res = Reservation(
                branch_id=branch_id,
                customer_name=form.customer_name.data,
                customer_email=form.customer_email.data,
                customer_phone=form.customer_phone.data,
                party_size=form.party_size.data,
                reserved_at=reserved_at,
                table_id=table_id if table_id != 0 else None,
                notes=form.notes.data,
                status='pending'
            )

            db.session.add(res)
            db.session.commit()
            flash('Reservation created', 'success')
        except Exception as e:
            db.session.rollback()
            flash(str(e), 'error')
        return redirect(url_for('reservations.index'))

    # Query reservations for today and future
    reservations = Reservation.query.filter(
        Reservation.branch_id == current_user.branch_id,
        Reservation.reserved_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
    ).order_by(Reservation.reserved_at).all()

    return render_template('app/reservations.html',
                           reservations=reservations,
                           tables=tables,
                           form=form)


@reservations_bp.route('/<int:id>/status', methods=['POST'])
@login_required
def status(id):
    """Updates reservation status."""
    res = db.session.get(Reservation, id)
    if res is None: abort(404)
    if res.branch_id != current_user.branch_id:
        flash('Access denied', 'error')
        return redirect(url_for('reservations.index'))
    new_status = request.form.get('status')
    if new_status in ('confirmed', 'seated', 'cancelled', 'no_show'):
        res.status = new_status
        # If seated, mark the table as reserved
        if new_status == 'seated' and res.table_id:
            table = db.session.get(RestaurantTable, res.table_id)
            if table:
                table.status = 'occupied'
        db.session.commit()
        flash(f'Reservation {new_status}', 'success')
    return redirect(url_for('reservations.index'))


@reservations_bp.route('/<int:id>', methods=['DELETE'])
@login_required
def delete(id):
    """Cancels a reservation."""
    res = db.session.get(Reservation, id)
    if res is None: abort(404)
    if res.branch_id != current_user.branch_id:
        return success_response({'error': 'Access denied'}, 403)
    res.status = 'cancelled'
    db.session.commit()
    return success_response()
