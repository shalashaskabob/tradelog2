from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

db = SQLAlchemy()
migrate = Migrate()

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

    from app.routes import bp as main_blueprint
    app.register_blueprint(main_blueprint)

    from app import models

    return app 