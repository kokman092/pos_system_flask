"""Email Service"""
from datetime import datetime
from extensions import db
from app.models import EmailLog, EmailTemplate, EmailRecipient

def queue_email(recipient_email: str, subject: str, body_html: str, template_id: int = None, reference_type: str = None, reference_id: int = None) -> EmailLog:
    """Queues an email to be sent."""
    log = EmailLog(
        recipient_email=recipient_email,
        subject=subject,
        template_id=template_id,
        reference_type=reference_type,
        reference_id=reference_id,
        status='pending',
        retry_count=0
    )
    db.session.add(log)
    db.session.commit()
    return log

def queue_from_template(trigger_event: str, recipient_email: str, context: dict) -> EmailLog:
    """Queues an email based on an active template."""
    from jinja2 import Template
    template = EmailTemplate.query.filter_by(trigger_event=trigger_event, is_active=1).first()
    if not template:
        raise ValueError(f"No active template for {trigger_event}")
        
    jinja_template = Template(template.body_html)
    rendered_body = jinja_template.render(**context)
    
    return queue_email(
        recipient_email=recipient_email,
        subject=template.subject,
        body_html=rendered_body,
        template_id=template.template_id
    )

def process_pending_emails(app, mail, limit: int = 10) -> dict:
    """Processes pending emails (to be called by APScheduler)."""
    # Requires Flask-Mail instances passed
    # Assuming standard message format
    from flask_mail import Message
    with app.app_context():
        pending = EmailLog.query.filter_by(status='pending').limit(limit).all()
        sent = 0
        failed = 0
        for log in pending:
            try:
                body = ""
                if log.template_id:
                    t = db.session.get(EmailTemplate, log.template_id)
                    if t:
                        body = t.body_html
                msg = Message(subject=log.subject, recipients=[log.recipient_email], html=body)
                mail.send(msg)
                log.status = 'sent'
                log.sent_at = datetime.utcnow()
                sent += 1
            except Exception as e:
                log.retry_count += 1
                log.error_message = str(e)[:500]
                if log.retry_count >= 3:
                    log.status = 'failed'
                failed += 1
        db.session.commit()
        return {"sent": sent, "failed": failed}

def send_receipt(order_id: int, payment_id: int, recipient_email: str) -> EmailLog:
    """Queues a receipt email."""
    from app.services.order_service import get_order_summary
    summary = get_order_summary(order_id)
    return queue_from_template(
        'order_paid',
        recipient_email,
        {'order': summary['order'], 'items': summary['items'], 'payments': summary['payments']}
    )

def send_low_stock_alert(ingredient_name: str, qty: float, branch_id: int) -> EmailLog:
    """Queues a low stock alert email."""
    managers = EmailRecipient.query.filter_by(branch_id=branch_id, recipient_type='manager', is_subscribed=1).all()
    logs = []
    for manager in managers:
        log = queue_from_template(
            'low_stock',
            manager.email,
            {'ingredient_name': ingredient_name, 'qty': qty}
        )
        if log:
            logs.append(log)
    return logs[0] if logs else None
