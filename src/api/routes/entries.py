
from flask import Blueprint, jsonify

from decorators import current_user, role_required
from extensions import db
from models import Role, TransferCompany, TransferEntry
from utils.errors import ApiError
from utils.permissions import load_day, require_open
from utils.validation import get_json, get_or_404, parse_int, parse_money

entries_bp = Blueprint("entries", __name__, url_prefix="/api/transfer-days")


@entries_bp.post("/<int:day_id>/entries")
@role_required(Role.TRANSFER_AGENT, Role.MANAGER)
def add_entry(day_id):
    """Example: the manager adds a new company in the afternoon; today's close needs its column."""
    day = load_day(current_user(), day_id)
    require_open(day)
    company_id = parse_int(get_json().get(
        "company_id"), "company_id", minimum=1)
    company = get_or_404(TransferCompany, company_id, "Company")
    if not company.is_active:
        raise ApiError("This company is inactive.", field="company_id")
    if any(e.company_id == company.id for e in day.entries):
        raise ApiError(f"{company.name} is already on this day.",
                       409, field="company_id")

    entry = TransferEntry(day=day, company=company)
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.serialize()), 201


@entries_bp.put("/<int:day_id>/entries/<int:entry_id>")
@role_required(Role.TRANSFER_AGENT, Role.MANAGER)
def update_entry(day_id, entry_id):
    day = load_day(current_user(), day_id)
    require_open(day)
    entry = get_or_404(TransferEntry, entry_id, "Entry")
    if entry.day_id != day.id:
        # The URL says day 5, the entry belongs to day 4: refuse.
        raise ApiError("Entry not found.", 404)

    data = get_json()
    if "cash_amount" in data:
        cash = parse_money(data["cash_amount"], "cash_amount")
        if cash < entry.refunds_total:
            raise ApiError(
                f"{entry.company.name} already has ${entry.refunds_total} in refunds today. "
                "Cash received can't be lower than that.",
                field="cash_amount",
            )
        entry.cash_amount = cash
    if "card_amount" in data:
        card = parse_money(data["card_amount"], "card_amount")
        if card > 0 and not entry.company.accepts_card:
            raise ApiError(
                f"{entry.company.name} doesn't take card payments.", field="card_amount")
        entry.card_amount = card

    db.session.commit()
    return jsonify(entry.serialize()), 200
