from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.login_message = 'Please log in to access this page.'
login.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Create the instance folder if it doesn't exist.
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.split('sqlite:///')[1]
        instance_path = os.path.dirname(db_path)
        if not os.path.exists(instance_path):
            os.makedirs(instance_path)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    # Import models here so that they are registered with SQLAlchemy
    from app import models

    from app.routes import bp as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.auth.routes import bp as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from app import cli
    cli.register_commands(app)

    @app.before_request
    def update_last_seen():
        from flask_login import current_user
        from datetime import datetime
        if current_user.is_authenticated:
            current_user.last_seen = datetime.utcnow()
            db.session.commit()

    return app 