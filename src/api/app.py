# app.py
from flask import Flask
from flask_cors import CORS
from config import Config
from extensions import db, migrate, jwt


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"].split(","))

    import models

    from routes.auth import auth_bp
    from routes.register import register_bp
    from routes.transfer import transfer_bp
    from routes.notes import notes_bp
    from routes.users import users_bp
    for bp in (auth_bp, register_bp, transfer_bp, notes_bp, users_bp):
        app.register_blueprint(bp)

    return app

app = create_app()
