
from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db
from models import User
from utils.errors import ApiError


def current_user():
    identity = get_jwt_identity()

    if g.get("current_user_identity") != identity:
        g.current_user_identity = identity
        g.current_user = db.session.get(
            User, int(identity)) if identity else None
    return g.current_user


def _check_active():
    verify_jwt_in_request()
    user = current_user()

    if user is None or not user.is_active:
        raise ApiError("Your account is disabled. Ask a manager.", 401)
    return user


def login_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        _check_active()
        return fn(*args, **kwargs)
    return inner


def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            user = _check_active()
            if user.role not in roles:
                raise ApiError("You don't have access to this page.", 403)
            return fn(*args, **kwargs)
        return inner
    return wrapper
