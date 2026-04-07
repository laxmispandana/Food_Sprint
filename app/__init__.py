import os

from dotenv import load_dotenv
from flask import Flask

from .extensions import db, migrate
from .routes import main_bp
from .services.data_seed import seed_data


def create_app():
    load_dotenv()
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///food_ordering.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SPOONACULAR_API_KEY"] = os.getenv("SPOONACULAR_API_KEY", "")
    app.config["RAZORPAY_KEY_ID"] = os.getenv("RAZORPAY_KEY_ID", "")
    app.config["RAZORPAY_KEY_SECRET"] = os.getenv("RAZORPAY_KEY_SECRET", "")
    app.config["APP_BASE_URL"] = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
    app.config["ADMIN_EMAIL"] = os.getenv("ADMIN_EMAIL", "admin@telanganaeats.local")
    app.config["ADMIN_PASSWORD"] = os.getenv("ADMIN_PASSWORD", "admin123")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        from . import models

        db.create_all()
        seed_data()

    app.register_blueprint(main_bp)
    return app
