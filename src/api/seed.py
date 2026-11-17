
from app import app
from extensions import db
from models import User, Role, seed_companies

USERS = [
    {"name": "Admin Manager",  "username": "manager",
        "password": "ChangeMe123!", "role": Role.MANAGER},
    {"name": "Test Cashier",   "username": "cashier",
        "password": "1234",         "role": Role.CASHIER},
    {"name": "Transfer Agent", "username": "agent",
        "password": "1234",         "role": Role.TRANSFER_AGENT},
]


def seed_users():
    for data in USERS:
        if User.query.filter_by(username=data["username"]).first():
            print(f"  skipped (exists): {data['username']}")
            continue
        user = User(name=data["name"], username=data["username"],
                    role=data["role"], is_active=True)

        user.set_password(data["password"])
        db.session.add(user)
        print(f"  created: {data['username']} ({data['role'].value})")
    db.session.commit()


def run():
    with app.app_context():
        print("Seeding users...")
        seed_users()
        print("Seeding transfer companies...")
        seed_companies()
        print("Done.")


if __name__ == "__main__":
    run()
