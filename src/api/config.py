import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _database_url():
    """Use DATABASE_URL if set, otherwise a local SQLite file.
    Render/Heroku give 'postgres://', but SQLAlchemy needs 'postgresql://'."""
    url = os.environ.get("DATABASE_URL", "sqlite:///caribbean_market.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    ENV_NAME = os.environ.get("APP_ENV", "development")
    IS_PRODUCTION = ENV_NAME == "production"

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.environ.get("FLASK_APP_KEY", "dev-only-flask-key")

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        if IS_PRODUCTION:

            raise RuntimeError(
                "JWT_SECRET_KEY is missing. Set it in the server's environment.")
        JWT_SECRET_KEY = "dev-only-secret"

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.environ.get("JWT_HOURS", 12)))

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
