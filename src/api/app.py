import click
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from config import Config
from extensions import db, jwt, migrate
from utils.errors import ApiError


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    import models

    register_blueprints(app)
    register_error_handlers(app)
    register_commands(app)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    return app


def register_blueprints(app):
    from routes.auth import auth_bp
    from routes.companies import companies_bp
    from routes.counts import counts_bp
    from routes.entries import entries_bp
    from routes.notes import notes_bp
    from routes.overview import overview_bp
    from routes.refunds import refunds_bp
    from routes.register import register_bp
    from routes.transfer_days import transfer_days_bp
    from routes.users import users_bp

    for bp in (auth_bp, users_bp, companies_bp, register_bp, transfer_days_bp,
               entries_bp, refunds_bp, counts_bp, notes_bp, overview_bp):
        app.register_blueprint(bp)


def register_error_handlers(app):
    """Every error leaves the API as JSON {"msg": ...}, so React always reads errors the same way."""

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        db.session.rollback()
        return jsonify(error.to_dict()), error.status

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error):
        # The database refused something (duplicate, broken constraint).
        db.session.rollback()
        return jsonify({"msg": "This conflicts with data that already exists."}), 409

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({"msg": error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        db.session.rollback()
        # full details go to the server log, never to the user
        app.logger.exception(error)
        return jsonify({"msg": "Something went wrong on the server."}), 500

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({"msg": "Please sign in."}), 401

    @jwt.expired_token_loader
    def expired_token(header, payload):
        return jsonify({"msg": "Your session expired. Please sign in again."}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify({"msg": "Please sign in again."}), 401


def register_commands(app):
    from models import Role, User, seed_companies

    @app.cli.command("seed-companies")
    def seed_companies_command():
        """Create the 7 transfer companies."""
        seed_companies()
        click.echo("Companies ready.")

    @app.cli.command("create-manager")
    @click.option("--name", prompt=True)
    @click.option("--username", prompt=True)
    @click.password_option()
    def create_manager_command(name, username, password):
        """Create the first manager (nobody can log in before that)."""
        username = username.strip().lower()
        if User.query.filter_by(username=username).first():
            raise click.ClickException("That username already exists.")
        user = User(name=name.strip(), username=username, role=Role.MANAGER)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Manager {username} created.")


app = create_app()
