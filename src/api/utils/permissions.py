
from models import DayStatus, ReportStatus, RegisterReport, TransferDay
from utils.errors import ApiError
from utils.validation import get_or_404


def load_report(user, report_id):
    report = get_or_404(RegisterReport, report_id, "Register report")
    if not user.is_manager and report.cashier_id != user.id:
        # 404, not 403: a cashier shouldn't even learn that another report exists.
        raise ApiError("Register report not found.", 404)
    return report


def require_draft(report):
    if report.status != ReportStatus.DRAFT:
        raise ApiError(
            "This report was already submitted. Ask a manager to reopen it.", 409)


def load_day(user, day_id):
    day = get_or_404(TransferDay, day_id, "Transfer day")
    if not user.is_manager and day.agent_id != user.id:
        raise ApiError("Transfer day not found.", 404)
    return day


def require_open(day):
    if day.status != DayStatus.OPEN:
        raise ApiError("This day is closed. Ask a manager to reopen it.", 409)
