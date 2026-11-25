
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from decorators import current_user, role_required
from extensions import db
from models import BILL_DENOMINATIONS, RegisterReport, ReportStatus, Role, utcnow
from utils.dates import store_today
from utils.errors import ApiError
from utils.permissions import load_report, require_draft
from utils.validation import (
    get_json, optional_text, paginate, parse_date, parse_int, parse_money)

register_bp = Blueprint("register", __name__,
                        url_prefix="/api/register-reports")


@register_bp.get("")
@role_required(Role.CASHIER, Role.MANAGER)
def list_reports():
    user = current_user()
    query = RegisterReport.query.order_by(
        RegisterReport.report_date.desc(), RegisterReport.id.desc())

    if not user.is_manager:
        # a cashier only ever sees their own
        query = query.filter_by(cashier_id=user.id)
    elif request.args.get("cashier_id"):
        query = query.filter_by(cashier_id=parse_int(
            request.args["cashier_id"], "cashier_id", minimum=1))

    if request.args.get("date"):
        query = query.filter_by(
            report_date=parse_date(request.args["date"], "date"))
    if request.args.get("from"):
        query = query.filter(RegisterReport.report_date >=
                             parse_date(request.args["from"], "from"))
    if request.args.get("to"):
        query = query.filter(RegisterReport.report_date <=
                             parse_date(request.args["to"], "to"))
    if request.args.get("status"):
        try:
            query = query.filter_by(
                status=ReportStatus(request.args["status"]))
        except ValueError:
            raise ApiError(
                "status must be draft, submitted or reviewed.", field="status")

    return jsonify(paginate(query, lambda r: r.serialize())), 200


@register_bp.post("/today")
@role_required(Role.CASHIER)
def open_today():
    """POST, not GET: it can CREATE a row. A GET must never change data."""
    user = current_user()
    today = store_today()
    report = RegisterReport.query.filter_by(
        cashier_id=user.id, report_date=today).first()
    if report:
        return jsonify(report.serialize()), 200

    data = request.get_json(silent=True) or {}
    report = RegisterReport.start(
        user, today, register_number=optional_text(data, "register_number", 10))
    db.session.add(report)
    try:
        db.session.commit()
    except IntegrityError:
       
        db.session.rollback()
        report = RegisterReport.query.filter_by(
            cashier_id=user.id, report_date=today).first()
        return jsonify(report.serialize()), 200
    return jsonify(report.serialize()), 201


@register_bp.get("/<int:report_id>")
@role_required(Role.CASHIER, Role.MANAGER)
def get_report(report_id):
    return jsonify(load_report(current_user(), report_id).serialize()), 200


@register_bp.put("/<int:report_id>")
@role_required(Role.CASHIER, Role.MANAGER)
def update_report(report_id):
    report = load_report(current_user(), report_id)
    require_draft(report)
    data = get_json()

    total_sales = parse_money(
        data["total_sales"], "total_sales") if "total_sales" in data else report.total_sales
    card_total = parse_money(
        data["card_total"], "card_total") if "card_total" in data else report.card_total
    if card_total > total_sales:
        raise ApiError(
            "Credit/Debit/EBT can't be more than total sales.", field="card_total")

    report.total_sales = total_sales
    report.card_total = card_total
    if "register_number" in data:
        report.register_number = optional_text(data, "register_number", 10)
    db.session.commit()
    return jsonify(report.serialize()), 200


@register_bp.put("/<int:report_id>/bills")
@role_required(Role.CASHIER, Role.MANAGER)
def update_bills(report_id):
    report = load_report(current_user(), report_id)
    require_draft(report)
    lines = get_json().get("bills")
    if not isinstance(lines, list) or not lines:
        raise ApiError(
            "bills must be a list like [{\"denomination\": 100, \"quantity\": 7}].", field="bills")

    by_denomination = {bill.denomination: bill for bill in report.bills}
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
    return jsonify(report.serialize()), 200


@register_bp.post("/<int:report_id>/submit")
@role_required(Role.CASHIER)
def submit_report(report_id):
    user = current_user()
    report = load_report(user, report_id)
    require_draft(report)
    report.status = ReportStatus.SUBMITTED
    report.submitted_at = utcnow()
    db.session.commit()
    return jsonify(report.serialize()), 200


@register_bp.post("/<int:report_id>/reopen")
@role_required(Role.MANAGER)
def reopen_report(report_id):
    report = load_report(current_user(), report_id)
    if report.status != ReportStatus.SUBMITTED:
        raise ApiError("Only a submitted report can be reopened.", 409)
    report.status = ReportStatus.DRAFT
    report.submitted_at = None
    db.session.commit()
    return jsonify(report.serialize()), 200


@register_bp.post("/<int:report_id>/review")
@role_required(Role.MANAGER)
def review_report(report_id):
    manager = current_user()
    report = load_report(manager, report_id)
    if report.status != ReportStatus.SUBMITTED:
        raise ApiError("Only a submitted report can be reviewed.", 409)
    report.status = ReportStatus.REVIEWED
    report.reviewed_at = utcnow()
    report.reviewed_by = manager
    db.session.commit()
    return jsonify(report.serialize()), 200
