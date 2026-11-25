
from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from decorators import current_user, login_required, role_required
from extensions import db
from models import Department, Role, ShiftNote, User, utcnow
from utils.dates import store_today
from utils.errors import ApiError
from utils.validation import get_json, get_or_404, paginate, parse_date, parse_int, require_text

notes_bp = Blueprint("notes", __name__, url_prefix="/api/shift-notes")

# The department comes from the recipient's role. We DERIVE it instead of
# asking the frontend, so it can never be wrong.
DEPARTMENT_FOR_ROLE = {
    Role.CASHIER: Department.SALES_REGISTER,
    Role.TRANSFER_AGENT: Department.MONEY_TRANSFER,
}


def load_thread(user, note_id):
    note = get_or_404(ShiftNote, note_id, "Note")
    root = note.parent or note
    if not user.is_manager and user.id not in (root.author_id, root.recipient_id):
        raise ApiError("Note not found.", 404)
    return root


def unread_for(user, root):
    return [n for n in [root, *root.replies] if n.recipient_id == user.id and not n.is_read]


def serialize_thread(user, root):
    data = root.serialize()
    data["unread_count"] = len(unread_for(user, root))
    return data


@notes_bp.get("")
@login_required
def list_threads():
    user = current_user()
    query = ShiftNote.query.filter(ShiftNote.parent_id.is_(
        None)).order_by(ShiftNote.created_at.desc())
    if not user.is_manager:
        query = query.filter(
            or_(ShiftNote.author_id == user.id, ShiftNote.recipient_id == user.id))
    if request.args.get("date"):
        query = query.filter_by(
            shift_date=parse_date(request.args["date"], "date"))
    if request.args.get("unread") == "1":
        # conversations where the first note OR a reply is still unread for me
        unread_root_ids = db.session.query(db.func.coalesce(ShiftNote.parent_id, ShiftNote.id)).filter(
            ShiftNote.recipient_id == user.id, ShiftNote.read_at.is_(None)
        )
        query = query.filter(ShiftNote.id.in_(unread_root_ids))
    return jsonify(paginate(query, lambda root: serialize_thread(user, root))), 200


@notes_bp.get("/unread-count")
@login_required
def unread_count():
    count = ShiftNote.query.filter_by(
        recipient_id=current_user().id, read_at=None).count()
    return jsonify({"unread": count}), 200


@notes_bp.post("")
@role_required(Role.MANAGER)
def create_note():
    manager = current_user()
    data = get_json()
    recipient = get_or_404(User, parse_int(
        data.get("recipient_id"), "recipient_id", minimum=1), "Recipient")
    if not recipient.is_active:
        raise ApiError("This account is disabled.", field="recipient_id")
    if recipient.role not in DEPARTMENT_FOR_ROLE:
        raise ApiError(
            "Notes go to a cashier or a transfer agent.", field="recipient_id")

    shift_date = parse_date(data["shift_date"], "shift_date") if data.get(
        "shift_date") else store_today()
    note = ShiftNote(
        author=manager,
        recipient=recipient,
        shift_date=shift_date,
        department=DEPARTMENT_FOR_ROLE[recipient.role],
        text=require_text(data, "text", 2000),
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(serialize_thread(manager, note)), 201


@notes_bp.get("/<int:note_id>")
@login_required
def get_thread(note_id):
    user = current_user()
    return jsonify(serialize_thread(user, load_thread(user, note_id))), 200


@notes_bp.post("/<int:note_id>/replies")
@login_required
def reply(note_id):
    user = current_user()
    root = load_thread(user, note_id)
    if user.id not in (root.author_id, root.recipient_id):
        raise ApiError(
            "Only the two people in this conversation can reply.", 403)
    note = root.reply(user, require_text(get_json(), "text", 2000))
    db.session.add(note)
    db.session.commit()
    return jsonify(serialize_thread(user, root)), 201


@notes_bp.post("/<int:note_id>/read")
@login_required
def mark_read(note_id):
    user = current_user()
    root = load_thread(user, note_id)
    for note in unread_for(user, root):
        note.read_at = utcnow()
    db.session.commit()
    return jsonify(serialize_thread(user, root)), 200
