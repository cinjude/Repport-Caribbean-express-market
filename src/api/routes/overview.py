
from flask import Blueprint, jsonify

from decorators import current_user, role_required
from models import DayStatus, RegisterReport, ReportStatus, Role, ShiftNote, TransferDay

overview_bp = Blueprint("overview", __name__, url_prefix="/api/overview")


def register_summary(report):
    return {
        "id": report.id,
        "department": "sales_register",
        "date": report.report_date.isoformat(),
        "worked_by": report.cashier.name,
        "status": report.status.value,
        "total_sales": report.serialize()["total_sales"],
        "card_total": report.serialize()["card_total"],
        "expected": report.serialize()["cash_expected"],
        "counted": report.serialize()["cash_counted"],
        "difference": report.serialize()["difference"],
        "is_balanced": report.is_balanced,
    }


def transfer_summary(day):
    totals = day.serialize()["totals"]
    return {
        "id": day.id,
        "department": "money_transfer",
        "date": day.business_date.isoformat(),
        "worked_by": day.agent.name,
        "status": day.status.value,
        "expected": totals["expected_cash"],
        "refunds": totals["refunds_total"],
        "counted": totals["counted_cash"],
        "difference": totals["difference"],
        "is_balanced": day.is_balanced,
    }


@overview_bp.get("")
@role_required(Role.MANAGER)
def overview():
    manager = current_user()
    latest_report = RegisterReport.query.order_by(
        RegisterReport.report_date.desc()).first()
    latest_day = TransferDay.query.order_by(
        TransferDay.business_date.desc()).first()

    waiting = (
        [register_summary(r) for r in RegisterReport.query.filter_by(
            status=ReportStatus.SUBMITTED)]
        + [transfer_summary(d)
           for d in TransferDay.query.filter_by(status=DayStatus.CLOSED)]
    )
    waiting.sort(key=lambda item: item["date"], reverse=True)

    return jsonify({
        "latest_register_report": register_summary(latest_report) if latest_report else None,
        "latest_transfer_day": transfer_summary(latest_day) if latest_day else None,
        "waiting_for_review": waiting,
        "my_unread_notes": ShiftNote.query.filter_by(recipient_id=manager.id, read_at=None).count(),
        "sent_notes_unread": ShiftNote.query.filter_by(author_id=manager.id, read_at=None).count(),
    }), 200
