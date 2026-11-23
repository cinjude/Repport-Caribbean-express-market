
from flask import Blueprint, jsonify
from flask_jwt_extended import create_access_token

from decorators import current_user, login_required
from models import User
from utils.errors import ApiError
from utils.validation import get_json

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    data = get_json()
    username = str(data.get("username") or "").strip().lower()
    password = str(data.get("password") or "")

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        raise ApiError("Wrong username or password.", 401)
    if not user.is_active:
        raise ApiError("This account is disabled. Ask a manager.", 403)

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role.value},
    )
    return jsonify({"token": token, "user": user.serialize()}), 200


@auth_bp.get("/me")
@login_required
def me():
    return jsonify(current_user().serialize()), 200
