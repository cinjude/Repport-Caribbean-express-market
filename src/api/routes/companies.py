
from flask import Blueprint, jsonify, request

from decorators import current_user, role_required
from extensions import db
from models import Role, TransferCompany
from utils.errors import ApiError
from utils.validation import get_json, get_or_404, parse_bool, parse_int, require_text

companies_bp = Blueprint("companies", __name__, url_prefix="/api/companies")


def _name_taken(name, exclude_id=None):
    query = TransferCompany.query.filter(
        db.func.lower(TransferCompany.name) == name.lower())
    if exclude_id:
        query = query.filter(TransferCompany.id != exclude_id)
    return query.first() is not None


@companies_bp.get("")
@role_required(Role.MANAGER, Role.TRANSFER_AGENT)
def list_companies():
    query = TransferCompany.query.order_by(
        TransferCompany.sort_order, TransferCompany.name)
    if not (current_user().is_manager and request.args.get("include_inactive") == "1"):
        query = query.filter_by(is_active=True)
    return jsonify([c.serialize() for c in query.all()]), 200


@companies_bp.post("")
@role_required(Role.MANAGER)
def create_company():
    data = get_json()
    name = require_text(data, "name", 50)
    if _name_taken(name):
        raise ApiError(
            "A company with this name already exists.", 409, field="name")
    company = TransferCompany(
        name=name,
        accepts_card=parse_bool(
            data.get("accepts_card", False), "accepts_card"),
        sort_order=parse_int(data.get("sort_order", 0),
                             "sort_order", maximum=1000),
    )
    db.session.add(company)
    db.session.commit()
    return jsonify(company.serialize()), 201


@companies_bp.put("/<int:company_id>")
@role_required(Role.MANAGER)
def update_company(company_id):
    company = get_or_404(TransferCompany, company_id, "Company")
    data = get_json()
    if "name" in data:
        name = require_text(data, "name", 50)
        if _name_taken(name, exclude_id=company.id):
            raise ApiError(
                "A company with this name already exists.", 409, field="name")
        company.name = name
    if "accepts_card" in data:
        company.accepts_card = parse_bool(data["accepts_card"], "accepts_card")
    if "is_active" in data:
        company.is_active = parse_bool(
            data["is_active"], "is_active")  # hide, never delete
    if "sort_order" in data:
        company.sort_order = parse_int(
            data["sort_order"], "sort_order", maximum=1000)
    db.session.commit()
    return jsonify(company.serialize()), 200
