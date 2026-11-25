
from flask import Blueprint, jsonify, request

from decorators import current_user, role_required
from extensions import db
from models import Role, User
from utils.errors import ApiError
from utils.validation import (
    USERNAME_RE, get_json, get_or_404, parse_bool, require_text)

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


def parse_role(value):
    try:
        return Role(value)
    except ValueError:
        raise ApiError(
            "role must be manager, transfer_agent or cashier.", field="role")


def parse_password(value):
    if not isinstance(value, str) or len(value) < 4:
        raise ApiError(
            "Password or PIN must be at least 4 characters.", field="password")
    return value


@users_bp.get("")
@role_required(Role.MANAGER)
def list_users():
    query = User.query.order_by(User.name)
    if request.args.get("role"):
        query = query.filter_by(role=parse_role(request.args["role"]))
    if request.args.get("active") == "1":
        query = query.filter_by(is_active=True)
    return jsonify([u.serialize() for u in query.all()]), 200


@users_bp.post("")
@role_required(Role.MANAGER)
def create_user():
    data = get_json()
    name = require_text(data, "name", 100)
    username = require_text(data, "username", 50).lower()
    if not USERNAME_RE.match(username):
        raise ApiError(
            "username: 3-50 characters, letters, numbers, dot, dash or underscore.", field="username")
    if User.query.filter_by(username=username).first():
        raise ApiError("That username is already taken.",
                       409, field="username")

    user = User(name=name, username=username,
                role=parse_role(data.get("role")))
    user.set_password(parse_password(data.get("password")))
    db.session.add(user)
    db.session.commit()
    return jsonify(user.serialize()), 201


@users_bp.get("/<int:user_id>")
@role_required(Role.MANAGER)
def get_user(user_id):
    return jsonify(get_or_404(User, user_id, "User").serialize()), 200


@users_bp.put("/<int:user_id>")
@role_required(Role.MANAGER)
def update_user(user_id):
    user = get_or_404(User, user_id, "User")
    me = current_user()
    data = get_json()

    if "name" in data:
        user.name = require_text(data, "name", 100)
    if "role" in data:
        new_role = parse_role(data["role"])
        if user.id == me.id and new_role != Role.MANAGER:
            raise ApiError(
                "You can't remove your own manager role.", field="role")
        user.role = new_role
    if "is_active" in data:
        active = parse_bool(data["is_active"], "is_active")
        if user.id == me.id and not active:
            raise ApiError("You can't disable your own account.",
                           field="is_active")
        user.is_active = active
    if "password" in data:
        # manager resets a forgotten PIN
        user.set_password(parse_password(data["password"]))

    db.session.commit()
    return jsonify(user.serialize()), 200
