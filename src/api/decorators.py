
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from models import User


def current_user():
    return User.query.get(int(get_jwt_identity()))


def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            user = current_user()
            if user is None or not user.is_active or user.role not in roles:
                return jsonify({"msg": "You don't have access to this page."}), 403
            return fn(*args, **kwargs)
        return inner
    return wrapper
