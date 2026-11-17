
from datetime import date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from extensions import db
from decorators import role_required, current_user
from models import Role, RegisterReport

register_bp = Blueprint("register", __name__,
                        url_prefix="/api/register-reports")


@register_bp.get("/today")
@jwt_required()
@role_required(Role.CASHIER, Role.MANAGER)
def get_today_report():
    user = current_user()
    report = RegisterReport.query.filter_by(
        cashier_id=user.id, report_date=date.today()).first()
    if report is None:
        report = RegisterReport.start(user, date.today())
        db.session.add(report)
        db.session.commit()
    return jsonify(report.serialize()), 200
