from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mod_report.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from app.routes import auth_bp, mod_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(mod_bp)

    with app.app_context():
        db.create_all()

    return app
