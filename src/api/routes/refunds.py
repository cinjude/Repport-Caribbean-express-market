
from decimal import Decimal

from flask import Blueprint, jsonify, request

from decorators import current_user, role_required
from extensions import db
from models import REFUND_REASONS, Refund, Role
from utils.errors import ApiError
from utils.permissions import load_day, require_open
from utils.validation import get_json, get_or_404, optional_text, parse_int, parse_money, require_text

refunds_bp = Blueprint("refunds", __name__, url_prefix="/api")


def parse_reason(value):
    if value not in REFUND_REASONS:
        raise ApiError("reason must be one of: " +
                       ", ".join(REFUND_REASONS) + ".", field="reason")
    return value


def entry_for_company(day, company_id):
    for entry in day.entries:
        if entry.company_id == company_id:
            return entry
    raise ApiError("This company is not on today's sheet.", field="company_id")


def check_room(entry, amount, already_counted=Decimal("0.00")):
    """A refund can't be bigger than what the company still has in the drawer.
    already_counted = this refund's old amount when we edit it (it is already inside net_cash)."""
    room = entry.net_cash + already_counted
    if amount > room:
        raise ApiError(
            f"A refund can't be more than {entry.company.name}'s net cash today (${room}).",
            field="amount",
        )


@refunds_bp.get("/transfer-days/<int:day_id>/refunds")
@role_required(Role.TRANSFER_AGENT, Role.MANAGER)
def list_refunds(day_id):
    day = load_day(current_user(), day_id)
    refunds = day.refunds if request.args.get(
        "include_voided") == "1" else day.active_refunds
    return jsonify([r.serialize() for r in refunds]), 200


@refunds_bp.post("/transfer-days/<int:day_id>/refunds")
@role_required(Role.TRANSFER_AGENT, Role.MANAGER)
def create_refund(day_id):
    user = current_user()
    day = load_day(user, day_id)
    require_open(day)
    data = get_json()

    company_id = parse_int(data.get("company_id"), "company_id", minimum=1)
    entry = entry_for_company(day, company_id)
    amount = parse_money(data.get("amount"), "amount", allow_zero=False)
    check_room(entry, amount)

    refund = Refund(
        day=day,
        company=entry.company,
        amount=amount,
        reason=parse_reason(data.get("reason", "Other")),
        reference=optional_text(data, "reference", 100),
        note=optional_text(data, "note", 1000),
        created_by=user,
    )
    db.session.add(refund)
    db.session.commit()
    return jsonify(refund.serialize()), 201


@refunds_bp.put("/refunds/<int:refund_id>")
@role_required(Role.MANAGER)
def update_refund(refund_id):
    refund = get_or_404(Refund, refund_id, "Refund")
    require_open(refund.day)
    if refund.is_voided:
        raise ApiError("A voided refund can't be edited.", 409)
    data = get_json()

    if "amount" in data:
        amount = parse_money(data["amount"], "amount", allow_zero=False)
        check_room(entry_for_company(refund.day, refund.company_id),
                   amount, already_counted=refund.amount)
        refund.amount = amount
    if "reason" in data:
        refund.reason = parse_reason(data["reason"])
    if "reference" in data:
        refund.reference = optional_text(data, "reference", 100)
    if "note" in data:
        refund.note = optional_text(data, "note", 1000)

    db.session.commit()
    return jsonify(refund.serialize()), 200


@refunds_bp.post("/refunds/<int:refund_id>/void")
@role_required(Role.MANAGER)
def void_refund(refund_id):
    refund = get_or_404(Refund, refund_id, "Refund")
    if refund.day.is_locked:
        raise ApiError("This day was reviewed and is locked.", 409)
    if refund.is_voided:
        raise ApiError("This refund is already voided.", 409)
    refund.void(current_user(), require_text(get_json(), "reason", 255))
    db.session.commit()
    return jsonify(refund.serialize()), 200
