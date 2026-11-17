from datetime import datetime, timezone
from decimal import Decimal
from extensions import db
import enum


def utcnow():
    return datetime.now(timezone.utc)


def money(value):
    return f"{Decimal(value or 0):.2f}"


BILL_DENOMINATIONS = (100, 50, 20, 10, 5, 1)


class Role(enum.Enum):
    MANAGER = "manager"
    TRANSFER_AGENT = "transfer_agent"
    CASHIER = "cashier"


class DayStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    REVIEWED = "reviewed"

class Department(enum.Enum):
    SALES_REGISTER = "sales_register"
    MONEY_TRANSFER = "money_transfer"


class ReportStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


def enum_column(enum_class, default):
    return db.Column(
        db.Enum(
            enum_class,
            native_enum=False,
            values_callable=lambda e: [member.value for member in e],
            length=20,
        ),
        nullable=False,
        default=default,
    )


REFUND_REASONS = (
    "Customer cancelled",
    "Transfer failed",
    "Wrong amount entered",
    "Payout to receiver",
    "Other",
)
