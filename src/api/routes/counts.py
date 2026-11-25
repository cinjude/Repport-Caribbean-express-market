
from flask import Blueprint, jsonify

from decorators import current_user, role_required
from extensions import db
from models import BILL_DENOMINATIONS, Advance, Role, User
from utils.errors import ApiError
from utils.permissions import load_day, require_open
from utils.validation import get_json, get_or_404, optional_text, parse_int, parse_money, require_text

counts_bp = Blueprint("counts", __name__, url_prefix="/api")

AGENT_OR_MANAGER = (Role.TRANSFER_AGENT, Role.MANAGER)


@counts_bp.put("/transfer-days/<int:day_id>/bills")
@role_required(*AGENT_OR_MANAGER)
def update_bills(day_id):
    day = load_day(current_user(), day_id)
    require_open(day)
    lines = get_json().get("bills")
    if not isinstance(lines, list) or not lines:
        raise ApiError(
            "bills must be a list like [{\"denomination\": 100, \"quantity\": 52}].", field="bills")

    by_denomination = {bill.denomination: bill for bill in day.bills}
    for line in lines:
        if not isinstance(line, dict):
            raise ApiError("Each bill line must be an object.", field="bills")
        denomination = parse_int(
            line.get("denomination"), "denomination", minimum=1, maximum=100)
        if denomination not in BILL_DENOMINATIONS:
            raise ApiError(
                f"${denomination} is not a bill we count.", field="bills")
        by_denomination[denomination].quantity = parse_int(
            line.get("quantity"), "quantity", maximum=100_000)

    db.session.commit()
    return jsonify(day.serialize()), 200


@counts_bp.post("/transfer-days/<int:day_id>/advances")
@role_required(*AGENT_OR_MANAGER)
def add_advance(day_id):
    day = load_day(current_user(), day_id)
    require_open(day)
    data = get_json()

    linked_user = None
    if data.get("user_id") is not None:
        linked_user = get_or_404(User, parse_int(
            data["user_id"], "user_id", minimum=1), "User")

    advance = Advance(
        day=day,
        person_name=require_text(data, "person_name", 100),
        amount=parse_money(data.get("amount"), "amount", allow_zero=False),
        note=optional_text(data, "note", 255),
        user=linked_user,
    )
    db.session.add(advance)
    db.session.commit()
    return jsonify(advance.serialize()), 201


@counts_bp.delete("/advances/<int:advance_id>")
@role_required(*AGENT_OR_MANAGER)
def delete_advance(advance_id):
    advance = get_or_404(Advance, advance_id, "Advance")

    day = load_day(current_user(), advance.day_id)
    require_open(day)
    db.session.delete(advance)
    db.session.commit()
    return "", 204
