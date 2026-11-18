from extensions import db
import enum
from datetime import datetime, timezone
from .base import utcnow, enum_column
from werkzeug.security import check_password_hash, generate_password_hash


class Role(enum.Enum):
    MANAGER = "manager"
    TRANSFER_AGENT = "transfer_agent"
    CASHIER = "cashier"


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True,
                         nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = enum_column(Role, default=Role.CASHIER)
    is_active = db.Column(db.Boolean, nullable=False,
                          default=True)
    created_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow)

    register_reports = db.relationship(
        "RegisterReport",
        foreign_keys="RegisterReport.cashier_id",
        back_populates="cashier",
    )

    def set_password(self, raw_password):
        if not raw_password or len(raw_password) < 4:
            raise ValueError("Password or PIN must be at least 4 characters.")
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def has_role(self, *roles):
        """user.has_role(Role.MANAGER, Role.CASHIER) -> True / False"""
        return self.role in roles

    @property
    def is_manager(self):
        return self.role == Role.MANAGER

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "role": self.role.value,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"
