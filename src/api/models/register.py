from extensions import db
import enum
from .base import utcnow, money, enum_column, BILL_DENOMINATIONS
from decimal import Decimal
from sqlalchemy import Numeric, UniqueConstraint, CheckConstraint


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


class RegisterReport(db.Model):
    __tablename__ = "register_report"

    id = db.Column(db.Integer, primary_key=True)
    report_date = db.Column(db.Date, nullable=False, index=True)
    cashier_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False)
    register_number = db.Column(db.String(10), nullable=True)

    total_sales = db.Column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    card_total = db.Column(Numeric(10, 2), nullable=False,
                           default=Decimal("0.00"))  # Credit/Debit/EBT

    status = enum_column(ReportStatus, default=ReportStatus.DRAFT)
    submitted_at = db.Column(db.DateTime(timezone=True))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    created_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("cashier_id", "report_date",
                         name="uq_register_report_cashier_day"),
        CheckConstraint("total_sales >= 0",
                        name="ck_register_report_sales_positive"),
        CheckConstraint("card_total >= 0",
                        name="ck_register_report_card_positive"),
        CheckConstraint("card_total <= total_sales",
                        name="ck_register_report_card_le_sales"),
    )

    cashier = db.relationship("User", foreign_keys=[
                              cashier_id], back_populates="register_reports")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    bills = db.relationship(
        "RegisterBillCount",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="RegisterBillCount.denomination.desc()",
    )

    @classmethod
    def start(cls, cashier, report_date, register_number=None):
        report = cls(cashier=cashier, report_date=report_date,
                     register_number=register_number)
        report.bills = [RegisterBillCount(
            denomination=d, quantity=0) for d in BILL_DENOMINATIONS]
        return report

    @property
    def cash_expected(self):
        """Total sales - Credit/Debit/EBT. Example: 4609.40 - 2753.40 = 1856.00"""
        return Decimal(self.total_sales or 0) - Decimal(self.card_total or 0)

    @property
    def cash_counted(self):
        return sum((bill.amount for bill in self.bills), Decimal("0.00"))

    @property
    def difference(self):
        """Positive = over, negative = short, 0 = balanced."""
        return self.cash_counted - self.cash_expected

    @property
    def is_balanced(self):
        return self.difference == 0

    @property
    def is_locked(self):
        return self.status == ReportStatus.REVIEWED

    def serialize(self):
        return {
            "id": self.id,
            "report_date": self.report_date.isoformat(),
            "cashier": {"id": self.cashier.id, "name": self.cashier.name} if self.cashier else None,
            "register_number": self.register_number,
            "total_sales": money(self.total_sales),
            "card_total": money(self.card_total),
            "cash_expected": money(self.cash_expected),
            "cash_counted": money(self.cash_counted),
            "difference": money(self.difference),
            "is_balanced": self.is_balanced,
            "status": self.status.value,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "bills": [bill.serialize() for bill in self.bills],
        }

    def __repr__(self):
        return f"<RegisterReport {self.report_date} cashier={self.cashier_id}>"


class RegisterBillCount(db.Model):
    __tablename__ = "register_bill_count"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey("register_report.id", ondelete="CASCADE"),
        nullable=False,
    )
    denomination = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("report_id", "denomination",
                         name="uq_bill_report_denomination"),
        CheckConstraint("denomination IN (1, 5, 10, 20, 50, 100)",
                        name="ck_bill_valid_denomination"),
        CheckConstraint("quantity >= 0", name="ck_bill_quantity_positive"),
    )

    report = db.relationship("RegisterReport", back_populates="bills")

    @property
    def amount(self):
        return Decimal(self.denomination) * self.quantity

    def serialize(self):
        return {
            "denomination": self.denomination,
            "quantity": self.quantity,
            "amount": money(self.amount),
        }
