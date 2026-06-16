from .auth import auth_bp
from .dashboard import dashboard_bp
from .pos import pos_bp
from .kitchen import kitchen_bp
from .kds import kds_bp
from .menu import menu_bp
from .inventory import inventory_bp
from .reservations import reservations_bp
from .employees import employees_bp
from .loyalty import loyalty_bp
from .reports import reports_bp
from .settings import settings_bp
from .offline_sync import offline_sync_bp
from .tables import tables_bp
from .roles import roles_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(kitchen_bp)
    app.register_blueprint(kds_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(reservations_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(loyalty_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(offline_sync_bp)
    app.register_blueprint(tables_bp)
    app.register_blueprint(roles_bp)
