from decimal import Decimal
from sqlalchemy import Numeric, UniqueConstraint, CheckConstraint
from extensions import db
from models.base import money, utcnow, enum_column, BILL_DENOMINATIONS, DayStatus


class TransferCompany(db.Model):
    __tablename__ = "transfer_company"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    accepts_card = db.Column(db.Boolean, nullable=False,
                             default=False)  # Vigo = True
    is_active = db.Column(db.Boolean, nullable=False,
                          default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "accepts_card": self.accepts_card,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
        }

    def __repr__(self):
        return f"<TransferCompany {self.name}>"


class TransferDay(db.Model):
    __tablename__ = "transfer_day"

    id = db.Column(db.Integer, primary_key=True)
    business_date = db.Column(db.Date, nullable=False,
                              unique=True, index=True)  # one close per day
    agent_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # --- what the agent types during the count ---
    coins = db.Column(Numeric(10, 2), nullable=False,
                      default=Decimal("0.00"))        # added to counted
    change_fund = db.Column(Numeric(10, 2), nullable=False, default=Decimal(
        "0.00"))  # kept for tomorrow, NOT counted
    note = db.Column(db.Text)  # explanation if the drawer is short / over

    # --- workflow ---
    status = enum_column(DayStatus, default=DayStatus.OPEN)
    closed_at = db.Column(db.DateTime(timezone=True))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    created_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint("coins >= 0", name="ck_transfer_day_coins_positive"),
        CheckConstraint("change_fund >= 0",
                        name="ck_transfer_day_change_positive"),
    )

    agent = db.relationship("User", foreign_keys=[agent_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    entries = db.relationship(
        "TransferEntry", back_populates="day", cascade="all, delete-orphan")
    refunds = db.relationship(
        "Refund", back_populates="day", cascade="all, delete-orphan", order_by="Refund.created_at"
    )
    bills = db.relationship(
        "TransferBillCount",
        back_populates="day",
        cascade="all, delete-orphan",
        order_by="TransferBillCount.denomination.desc()",
    )
    advances = db.relationship(
        "Advance", back_populates="day", cascade="all, delete-orphan")

    # ---- factory: one entry per active company + the 6 bill lines ----
    @classmethod
    def start(cls, agent, business_date):
        day = cls(agent=agent, business_date=business_date)
        companies = (
            TransferCompany.query.filter_by(is_active=True)
            .order_by(TransferCompany.sort_order, TransferCompany.name)
            .all()
        )
        day.entries = [TransferEntry(company=c) for c in companies]
        day.bills = [TransferBillCount(denomination=d, quantity=0)
                     for d in BILL_DENOMINATIONS]
        return day

    # ---- calculated values ----
    @property
    def active_refunds(self):
        """Voided refunds stay in the database for history but don't count."""
        return [r for r in self.refunds if not r.is_voided]

    @property
    def gross_cash(self):
        return sum((e.cash_amount for e in self.entries), Decimal("0.00"))

    @property
    def card_total(self):
        return sum((e.card_amount for e in self.entries), Decimal("0.00"))

    @property
    def refunds_total(self):
        return sum((r.amount for r in self.active_refunds), Decimal("0.00"))

    @property
    def expected_cash(self):
        """The GRAND TOTAL on the paper sheet: cash in - refunds. Example: 14548.65"""
        return self.gross_cash - self.refunds_total

    @property
    def bills_total(self):
        return sum((b.amount for b in self.bills), Decimal("0.00"))

    @property
    def advances_total(self):
        return sum((a.amount for a in self.advances), Decimal("0.00"))

    @property
    def counted_cash(self):
        """Bills + coins + advances. Example: 14481 + 0 + 67 = 14548.00"""
        return self.bills_total + Decimal(self.coins or 0) + self.advances_total

    @property
    def difference(self):
        """Positive = over, negative = short. Example: -0.65"""
        return self.counted_cash - self.expected_cash

    @property
    def is_balanced(self):
        return self.difference == 0

    @property
    def is_locked(self):
        return self.status == DayStatus.REVIEWED

    def refunds_for_company(self, company_id):
        return sum(
            (r.amount for r in self.active_refunds if r.company_id == company_id),
            Decimal("0.00"),
        )

    def serialize(self):
        return {
            "id": self.id,
            "business_date": self.business_date.isoformat(),
            "agent": {"id": self.agent.id, "name": self.agent.name} if self.agent else None,
            "status": self.status.value,
            "entries": [e.serialize() for e in self.entries],
            "refunds": [r.serialize() for r in self.refunds],
            "bills": [b.serialize() for b in self.bills],
            "advances": [a.serialize() for a in self.advances],
            "coins": money(self.coins),
            "change_fund": money(self.change_fund),
            "note": self.note,
            "totals": {
                "gross_cash": money(self.gross_cash),
                "card_total": money(self.card_total),
                "refunds_total": money(self.refunds_total),
                "expected_cash": money(self.expected_cash),
                "bills_total": money(self.bills_total),
                "advances_total": money(self.advances_total),
                "counted_cash": money(self.counted_cash),
                "difference": money(self.difference),
                "is_balanced": self.is_balanced,
            },
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

    def __repr__(self):
        return f"<TransferDay {self.business_date} {self.status.value}>"


class TransferEntry(db.Model):
    __tablename__ = "transfer_entry"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey(
        "transfer_day.id", ondelete="CASCADE"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey(
        "transfer_company.id"), nullable=False)
    cash_amount = db.Column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    card_amount = db.Column(Numeric(10, 2), nullable=False,
                            default=Decimal("0.00"))  # only Vigo today

    __table_args__ = (
        UniqueConstraint("day_id", "company_id",
                         name="uq_transfer_entry_day_company"),
        CheckConstraint("cash_amount >= 0",
                        name="ck_transfer_entry_cash_positive"),
        CheckConstraint("card_amount >= 0",
                        name="ck_transfer_entry_card_positive"),
    )

    day = db.relationship("TransferDay", back_populates="entries")
    company = db.relationship("TransferCompany")

    @property
    def refunds_total(self):
        return self.day.refunds_for_company(self.company_id) if self.day else Decimal("0.00")

    @property
    def net_cash(self):
        """Example Ria: 15716.50 - 5531.43 = 10185.07"""
        return Decimal(self.cash_amount or 0) - self.refunds_total

    def serialize(self):
        return {
            "id": self.id,
            "company": self.company.serialize() if self.company else None,
            "cash_amount": money(self.cash_amount),
            "card_amount": money(self.card_amount),
            "refunds_total": money(self.refunds_total),
            "net_cash": money(self.net_cash),
        }


class Refund(db.Model):
    __tablename__ = "refund"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey(
        "transfer_day.id", ondelete="CASCADE"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey(
        "transfer_company.id"), nullable=False)
    amount = db.Column(Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(50), nullable=False,
                       default="Other")  # one of REFUND_REASONS
    reference = db.Column(db.String(100))  # receipt / transfer number
    note = db.Column(db.Text)

    created_by_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow)

    # --- void instead of delete: history is never erased ---
    voided_at = db.Column(db.DateTime(timezone=True))
    voided_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    void_reason = db.Column(db.String(255))

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_refund_amount_positive"),
    )

    day = db.relationship("TransferDay", back_populates="refunds")
    company = db.relationship("TransferCompany")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    voided_by = db.relationship("User", foreign_keys=[voided_by_id])

    @property
    def is_voided(self):
        return self.voided_at is not None

    def void(self, manager, reason):
        """Only call this after checking manager.is_manager in the route."""
        self.voided_at = utcnow()
        self.voided_by = manager
        self.void_reason = reason

    def serialize(self):
        return {
            "id": self.id,
            "company": {"id": self.company.id, "name": self.company.name} if self.company else None,
            "amount": money(self.amount),
            "reason": self.reason,
            "reference": self.reference,
            "note": self.note,
            "created_by": {"id": self.created_by.id, "name": self.created_by.name} if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_voided": self.is_voided,
            "voided_at": self.voided_at.isoformat() if self.voided_at else None,
            "void_reason": self.void_reason,
        }


class TransferBillCount(db.Model):
    __tablename__ = "transfer_bill_count"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey(
        "transfer_day.id", ondelete="CASCADE"), nullable=False)
    denomination = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("day_id", "denomination",
                         name="uq_transfer_bill_day_denomination"),
        CheckConstraint("denomination IN (1, 5, 10, 20, 50, 100)",
                        name="ck_transfer_bill_valid_denomination"),
        CheckConstraint("quantity >= 0",
                        name="ck_transfer_bill_quantity_positive"),
    )

    day = db.relationship("TransferDay", back_populates="bills")

    @property
    def amount(self):
        return Decimal(self.denomination) * self.quantity

    def serialize(self):
        return {
            "denomination": self.denomination,
            "quantity": self.quantity,
            "amount": money(self.amount),
        }


class Advance(db.Model):
    __tablename__ = "advance"

    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey(
        "transfer_day.id", ondelete="CASCADE"), nullable=False)
    # text, because the person may not have an account
    person_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(
        "user.id"))  # optional link if they do
    amount = db.Column(Numeric(10, 2), nullable=False)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_advance_amount_positive"),
    )

    day = db.relationship("TransferDay", back_populates="advances")
    user = db.relationship("User")

    def serialize(self):
        return {
            "id": self.id,
            "person_name": self.person_name,
            "user_id": self.user_id,
            "amount": money(self.amount),
            "note": self.note,
        }


DEFAULT_COMPANIES = (
    ("Girosol", False),
    ("Vigo", True),
    ("Ria", False),
    ("Unidos", False),
    ("Black 011", False),
    ("Haiti", False),
    ("CAM NEW", False),
)


def seed_companies():
    for order, (name, accepts_card) in enumerate(DEFAULT_COMPANIES):
        if not TransferCompany.query.filter_by(name=name).first():
            db.session.add(TransferCompany(
                name=name, accepts_card=accepts_card, sort_order=order))
    db.session.commit()
