
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from decorators import current_user, role_required
from extensions import db
from models import DayStatus, Role, TransferDay, utcnow
from utils.dates import store_today
from utils.errors import ApiError
from utils.permissions import load_day, require_open
from utils.validation import get_json, optional_text, paginate, parse_date, parse_money

transfer_days_bp = Blueprint(
    "transfer_days", __name__, url_prefix="/api/transfer-days")

AGENT_OR_MANAGER = (Role.TRANSFER_AGENT, Role.MANAGER)


@transfer_days_bp.get("")
@role_required(*AGENT_OR_MANAGER)
def list_days():
    user = current_user()
    query = TransferDay.query.order_by(TransferDay.business_date.desc())
    if not user.is_manager:
        query = query.filter_by(agent_id=user.id)
    if request.args.get("date"):
        query = query.filter_by(
            business_date=parse_date(request.args["date"], "date"))
    if request.args.get("from"):
        query = query.filter(TransferDay.business_date >=
                             parse_date(request.args["from"], "from"))
    if request.args.get("to"):
        query = query.filter(TransferDay.business_date <=
                             parse_date(request.args["to"], "to"))
    if request.args.get("status"):
        try:
            query = query.filter_by(status=DayStatus(request.args["status"]))
        except ValueError:
            raise ApiError(
                "status must be open, closed or reviewed.", field="status")
    return jsonify(paginate(query, lambda d: d.serialize())), 200


@transfer_days_bp.post("/today")
@role_required(*AGENT_OR_MANAGER)
def open_today():
    user = current_user()
    today = store_today()
    day = TransferDay.query.filter_by(business_date=today).first()
    if day:
        if not user.is_manager and day.agent_id != user.id:
            raise ApiError(
                f"Today's close was opened by {day.agent.name}.", 409)
        return jsonify(day.serialize()), 200

    day = TransferDay.start(user, today)
    db.session.add(day)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        day = TransferDay.query.filter_by(business_date=today).first()
        return jsonify(day.serialize()), 200
    return jsonify(day.serialize()), 201


@transfer_days_bp.get("/<int:day_id>")
@role_required(*AGENT_OR_MANAGER)
def get_day(day_id):
    return jsonify(load_day(current_user(), day_id).serialize()), 200


@transfer_days_bp.put("/<int:day_id>")
@role_required(*AGENT_OR_MANAGER)
def update_day(day_id):
    day = load_day(current_user(), day_id)
    require_open(day)
    data = get_json()
    if "coins" in data:
        day.coins = parse_money(data["coins"], "coins")
    if "change_fund" in data:
        day.change_fund = parse_money(data["change_fund"], "change_fund")
    if "note" in data:
        day.note = optional_text(data, "note", 2000)
    db.session.commit()
    return jsonify(day.serialize()), 200


@transfer_days_bp.post("/<int:day_id>/close")
@role_required(*AGENT_OR_MANAGER)
def close_day(day_id):
    day = load_day(current_user(), day_id)
    require_open(day)
    if not day.is_balanced and not day.note:
        raise ApiError("The drawer is not balanced. Add a note explaining the difference before closing.",
                       field="note")
    day.status = DayStatus.CLOSED
    day.closed_at = utcnow()
    db.session.commit()
    return jsonify(day.serialize()), 200


@transfer_days_bp.post("/<int:day_id>/reopen")
@role_required(Role.MANAGER)
def reopen_day(day_id):
    day = load_day(current_user(), day_id)
    if day.status != DayStatus.CLOSED:
        raise ApiError("Only a closed day can be reopened.", 409)
    day.status = DayStatus.OPEN
    day.closed_at = None
    db.session.commit()
    return jsonify(day.serialize()), 200


@transfer_days_bp.post("/<int:day_id>/review")
@role_required(Role.MANAGER)
def review_day(day_id):
    manager = current_user()
    day = load_day(manager, day_id)
    if day.status != DayStatus.CLOSED:
        raise ApiError("Only a closed day can be reviewed.", 409)
    day.status = DayStatus.REVIEWED
    day.reviewed_at = utcnow()
    day.reviewed_by = manager
    db.session.commit()
    return jsonify(day.serialize()), 200
