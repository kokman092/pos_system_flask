from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_apscheduler import APScheduler

db = SQLAlchemy()
csrf = CSRFProtect()
login_manager = LoginManager()
cors = CORS()
migrate = Migrate()
bcrypt = Bcrypt()
mail = Mail()
scheduler = APScheduler()
