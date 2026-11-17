
from sqlalchemy import CheckConstraint
from extensions import db
from models.base import utcnow, enum_column, Department


class ShiftNote(db.Model):
    __tablename__ = "shift_note"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False)
    shift_date = db.Column(db.Date, nullable=False, index=True)
    department = enum_column(Department, default=Department.SALES_REGISTER)
    text = db.Column(db.Text, nullable=False)

    # A reply points to the first note of the conversation (the "thread").
    parent_id = db.Column(db.Integer, db.ForeignKey(
        "shift_note.id", ondelete="CASCADE"))

    # set when the recipient opens it
    read_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True),
                           nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint("author_id != recipient_id",
                        name="ck_shift_note_not_to_self"),
    )

    author = db.relationship("User", foreign_keys=[author_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])
    parent = db.relationship("ShiftNote", remote_side=[
                             id], back_populates="replies")
    replies = db.relationship(
        "ShiftNote",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="ShiftNote.created_at",
    )

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_read(self):
        if self.read_at is None:
            self.read_at = utcnow()

    def reply(self, author, text):
        """The reply goes back to whoever wrote the note we are answering."""
        root = self.parent or self
        recipient = self.author if author.id != self.author_id else self.recipient
        return ShiftNote(
            author=author,
            recipient=recipient,
            shift_date=root.shift_date,
            department=root.department,
            text=text,
            parent=root,
        )

    def serialize(self, include_replies=True):
        data = {
            "id": self.id,
            "author": {"id": self.author.id, "name": self.author.name, "role": self.author.role.value}
            if self.author else None,
            "recipient": {"id": self.recipient.id, "name": self.recipient.name}
            if self.recipient else None,
            "shift_date": self.shift_date.isoformat(),
            "department": self.department.value,
            "text": self.text,
            "parent_id": self.parent_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_replies:
            data["replies"] = [r.serialize(
                include_replies=False) for r in self.replies]
        return data
