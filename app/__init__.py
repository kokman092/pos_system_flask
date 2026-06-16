import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from config import config
from extensions import db, csrf, login_manager, cors, migrate, bcrypt, mail, scheduler


def configure_logging(app):
    """Sets up rotating file logging."""
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/aura_pos.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('AURA POS startup')


def configure_error_handlers(app):
    """Registers HTTP error handlers with proper DB cleanup."""
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f"Server Error: {error}")
        return render_template('errors/500.html'), 500


def create_app(config_name="default"):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Call init_app if the config class defines it (e.g. ProductionConfig validates SECRET_KEY)
    config_class = config[config_name]
    if hasattr(config_class, 'init_app'):
        config_class.init_app(app)

    # Initialize Extensions
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    cors.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    mail.init_app(app)
    scheduler.init_app(app)

    # Exempt JSON API routes from CSRF (they use session auth, not cookies with forms)
    csrf.exempt('pos.create_order')
    csrf.exempt('pos.add_item')
    csrf.exempt('pos.send_kitchen')
    csrf.exempt('pos.pay')
    csrf.exempt('pos.cancel')
    csrf.exempt('pos.discount')
    csrf.exempt('pos.delete_item')
    csrf.exempt('loyalty.search_customer')
    csrf.exempt('loyalty.create_customer')
    csrf.exempt('loyalty.get_customer')
    csrf.exempt('loyalty.redeem_points')
    csrf.exempt('kitchen.get_tickets')
    csrf.exempt('kitchen.serve')
    csrf.exempt('kitchen.warnings')
    csrf.exempt('offline_sync.sync_orders')

    # Logging
    if not app.testing:
        configure_logging(app)

    # Models & Login Loader
    from app import models
    from app.models import Employee

    @login_manager.user_loader
    def load_user(user_id):
        """Loads user by ID. Checks is_active AND email_verified."""
        user = db.session.get(Employee, int(user_id))
        if user and user.is_active == 1 and user.email_verified == 1:
            return user
        return None

    # Register Blueprints
    from app.routes import register_blueprints
    register_blueprints(app)

    # Error Handlers
    configure_error_handlers(app)

    # Start Scheduler
    if not app.testing:
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            if not scheduler.running:
                scheduler.start()
                app.logger.info("Scheduler started.")

            @scheduler.task('interval', id='process_emails', seconds=30)
            def process_emails():
                """Processes pending email queue."""
                with app.app_context():
                    try:
                        from app.services.email_service import process_pending_emails
                        process_pending_emails(app, mail, limit=10)
                    except Exception as e:
                        app.logger.error(f"Email job error: {e}")

            @scheduler.task('interval', id='low_stock_scan', minutes=15)
            def low_stock_scan():
                """Scans for low stock ingredients and sends alerts."""
                with app.app_context():
                    try:
                        from app.services.inventory_service import get_low_stock_items
                        from app.models import Branch
                        branches = Branch.query.filter_by(is_active=1).all()
                        for branch in branches:
                            items = get_low_stock_items(branch.branch_id)
                            if items:
                                app.logger.info(
                                    f"Low stock in branch {branch.branch_id}: "
                                    f"{len(items)} items"
                                )
                    except Exception as e:
                        app.logger.error(f"Low stock scan error: {e}")

    return app
