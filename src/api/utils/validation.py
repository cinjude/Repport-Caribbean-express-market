
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import request

from extensions import db
from utils.errors import ApiError

MAX_MONEY = Decimal("99999999.99")


def get_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Send the data as a JSON object.")
    return data


def parse_money(value, field, allow_zero=True):
    """'4609.4', 4609.4 or '4609.40' -> Decimal('4609.40')"""
    if value is None or isinstance(value, bool) or (isinstance(value, str) and not value.strip()):
        raise ApiError(f"{field} is required.", field=field)
    try:
        # str() first: Decimal(0.1) would keep the float's tiny binary error.
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ApiError(f"{field} must be a number.", field=field)
    if not amount.is_finite():
        raise ApiError(f"{field} must be a number.", field=field)
    if amount != amount.quantize(Decimal("0.01")):
        raise ApiError(f"{field} can have at most 2 decimals.", field=field)
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < 0:
        raise ApiError(f"{field} can't be negative.", field=field)
    if amount == 0 and not allow_zero:
        raise ApiError(f"{field} must be more than 0.", field=field)
    if amount > MAX_MONEY:
        raise ApiError(f"{field} is too large.", field=field)
    return amount


def parse_int(value, field, minimum=0, maximum=1_000_000):
    if isinstance(value, bool):
        raise ApiError(f"{field} must be a whole number.", field=field)
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a whole number.", field=field)
    if number < minimum or number > maximum:
        raise ApiError(
            f"{field} must be between {minimum} and {maximum}.", field=field)
    return number


def parse_bool(value, field):
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("1", "true", "yes"):
        return True
    if str(value).lower() in ("0", "false", "no"):
        return False
    raise ApiError(f"{field} must be true or false.", field=field)


def parse_date(value, field):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ApiError(f"{field} must be a date like 2026-10-24.", field=field)


def require_text(data, field, max_length):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"{field} is required.", field=field)
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(
            f"{field} must be {max_length} characters or less.", field=field)
    return value


def optional_text(data, field, max_length):
    value = data.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise ApiError(f"{field} must be text.", field=field)
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(
            f"{field} must be {max_length} characters or less.", field=field)
    return value


USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,50}$")


def get_or_404(model, object_id, label):
    obj = db.session.get(model, object_id)
    if obj is None:
        raise ApiError(f"{label} not found.", 404)
    return obj


def paginate(query, serializer):
    """?page=2&per_page=20 -> {"items": [...], "page": 2, "pages": 5, "total": 93}"""
    page = parse_int(request.args.get("page", 1), "page", minimum=1)
    per_page = parse_int(request.args.get("per_page", 30),
                         "per_page", minimum=1, maximum=100)
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [serializer(item) for item in result.items],
        "page": result.page,
        "pages": result.pages,
        "total": result.total,
    }
