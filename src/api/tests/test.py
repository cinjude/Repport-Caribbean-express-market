"""R  python -m pytest -q"""
import pytest

from app import create_app
from config import TestConfig
from extensions import db
from models import Role, User, seed_companies


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_companies()
        for name, username, role in [("Mgr", "manager", Role.MANAGER),
                                     ("Agent", "agent", Role.TRANSFER_AGENT),
                                     ("Cashier", "cashier", Role.CASHIER)]:
            u = User(name=name, username=username, role=role)
            u.set_password("1234")
            db.session.add(u)
        db.session.commit()
        yield app.test_client()
        db.drop_all()


def login(client, username):
    res = client.post("/api/auth/login",
                      json={"username": username, "password": "1234"})
    assert res.status_code == 200, res.json
    return {"Authorization": f"Bearer {res.json['token']}"}


def test_login(client):
    assert client.post(
        "/api/auth/login", json={"username": "manager", "password": "x"}).status_code == 401
    h = login(client, "Manager")  # usernames are case-insensitive
    assert client.get("/api/auth/me", headers=h).json["role"] == "manager"
    assert client.get("/api/auth/me").status_code == 401


def test_register_report_paper_sheet(client):
    c = login(client, "cashier")
    r = client.post("/api/register-reports/today",
                    headers=c, json={"register_number": "1"})
    assert r.status_code == 201
    rid = r.json["id"]
    assert client.post("/api/register-reports/today",
                       headers=c).status_code == 200  # same report again

    r = client.put(f"/api/register-reports/{rid}", headers=c,
                   json={"total_sales": "4609.40", "card_total": 2753.4})
    assert r.json["cash_expected"] == "1856.00"
    bills = [{"denomination": d, "quantity": q}
             for d, q in {100: 7, 50: 1, 20: 53, 10: 0, 5: 5, 1: 21}.items()]
    r = client.put(
        f"/api/register-reports/{rid}/bills", headers=c, json={"bills": bills})
    assert r.json["cash_counted"] == "1856.00" and r.json["is_balanced"]

    bad = client.put(
        f"/api/register-reports/{rid}", headers=c, json={"card_total": "9999"})
    assert bad.status_code == 400 and bad.json["field"] == "card_total"
    assert client.put(f"/api/register-reports/{rid}", headers=c, json={
                      "total_sales": "1.234"}).status_code == 400

    assert client.post(
        f"/api/register-reports/{rid}/submit", headers=c).json["status"] == "submitted"
    assert client.put(
        f"/api/register-reports/{rid}", headers=c, json={"total_sales": "1"}).status_code == 409

    m = login(client, "manager")
    assert client.post(
        f"/api/register-reports/{rid}/review", headers=m).json["status"] == "reviewed"
    assert client.get("/api/register-reports", headers=m).json["total"] == 1

    a = login(client, "agent")  # transfer agents never see sales reports
    assert client.get("/api/register-reports", headers=a).status_code == 403
    assert client.get(
        f"/api/register-reports/{rid}", headers=a).status_code == 403


def test_transfer_day_paper_sheet(client):
    a = login(client, "agent")
    day = client.post("/api/transfer-days/today", headers=a).json
    did = day["id"]
    entries = {e["company"]["name"]: e["id"] for e in day["entries"]}
    assert len(entries) == 7
    companies = {e["company"]["name"]: e["company"]["id"]
                 for e in day["entries"]}

    for name, cash in {"Girosol": "1792.60", "Vigo": "5751.97", "Ria": "15716.50", "Haiti": "133.00"}.items():
        assert client.put(f"/api/transfer-days/{did}/entries/{entries[name]}", headers=a,
                          json={"cash_amount": cash}).status_code == 200
    assert client.put(f"/api/transfer-days/{did}/entries/{entries['Vigo']}", headers=a,
                      json={"card_amount": "4836"}).status_code == 200
    assert client.put(f"/api/transfer-days/{did}/entries/{entries['Ria']}", headers=a,
                      # Ria takes no card
                      json={"card_amount": "5"}).status_code == 400

    too_big = client.post(f"/api/transfer-days/{did}/refunds", headers=a,
                          json={"company_id": companies["Haiti"], "amount": "500", "reason": "Transfer failed"})
    assert too_big.status_code == 400
    r1 = client.post(f"/api/transfer-days/{did}/refunds", headers=a,
                     json={"company_id": companies["Vigo"], "amount": "3313.99", "reason": "Customer cancelled"})
    r2 = client.post(f"/api/transfer-days/{did}/refunds", headers=a,
                     json={"company_id": companies["Ria"], "amount": "5531.43", "reason": "Transfer failed"})
    assert r1.status_code == r2.status_code == 201
    # cash can't drop below that company's refunds
    assert client.put(f"/api/transfer-days/{did}/entries/{entries['Ria']}", headers=a,
                      json={"cash_amount": "100"}).status_code == 400

    bills = [{"denomination": d, "quantity": q} for d, q in {
        100: 52, 50: 100, 20: 177, 10: 24, 5: 48, 1: 261}.items()]
    client.put(f"/api/transfer-days/{did}/bills",
               headers=a, json={"bills": bills})
    client.post(f"/api/transfer-days/{did}/advances",
                headers=a, json={"person_name": "Jude", "amount": "57"})
    adv = client.post(f"/api/transfer-days/{did}/advances",
                      headers=a, json={"person_name": "Theo", "amount": 10})
    client.put(f"/api/transfer-days/{did}",
               headers=a, json={"change_fund": "14"})

    totals = client.get(f"/api/transfer-days/{did}", headers=a).json["totals"]
    assert totals["expected_cash"] == "14548.65"
    assert totals["counted_cash"] == "14548.00"
    assert totals["difference"] == "-0.65"

    no_note = client.post(f"/api/transfer-days/{did}/close", headers=a)
    assert no_note.status_code == 400 and no_note.json["field"] == "note"
    client.put(f"/api/transfer-days/{did}", headers=a,
               json={"note": "Recounted twice, 65 cents missing."})
    assert client.post(
        f"/api/transfer-days/{did}/close", headers=a).json["status"] == "closed"
    assert client.delete(
        # closed
        f"/api/advances/{adv.json['id']}", headers=a).status_code == 409

    # agent can't void; manager can
    assert client.post(
        f"/api/refunds/{r1.json['id']}/void", headers=a, json={"reason": "x"}).status_code == 403
    m = login(client, "manager")
    v = client.post(
        f"/api/refunds/{r1.json['id']}/void", headers=m, json={"reason": "Entered twice"})
    assert v.json["is_voided"]
    assert client.get(
        f"/api/transfer-days/{did}", headers=m).json["totals"]["refunds_total"] == "5531.43"

    ov = client.get("/api/overview", headers=m).json
    assert ov["waiting_for_review"][0]["department"] == "money_transfer"
    assert client.post(
        f"/api/transfer-days/{did}/review", headers=m).json["status"] == "reviewed"

    c = login(client, "cashier")  # cashiers never see transfers
    assert client.get(
        f"/api/transfer-days/{did}", headers=c).status_code == 403
    assert client.get("/api/companies", headers=c).status_code == 403


def test_shift_notes(client):
    m = login(client, "manager")
    a = login(client, "agent")
    c = login(client, "cashier")
    agent_id = client.get("/api/auth/me", headers=a).json["id"]

    note = client.post("/api/shift-notes", headers=m,
                       json={"recipient_id": agent_id, "text": "Drawer short $0.65"})
    assert note.status_code == 201 and note.json["department"] == "money_transfer"
    nid = note.json["id"]

    assert client.get("/api/shift-notes/unread-count",
                      headers=a).json["unread"] == 1
    # not her conversation
    assert client.get(f"/api/shift-notes/{nid}", headers=c).status_code == 404
    assert client.post("/api/shift-notes", headers=a,
                       json={"recipient_id": 1, "text": "hi"}).status_code == 403

    reply = client.post(
        f"/api/shift-notes/{nid}/replies", headers=a, json={"text": "I recounted."})
    assert reply.json["replies"][0]["recipient"]["name"] == "Mgr"
    client.post(f"/api/shift-notes/{nid}/read", headers=a)
    assert client.get("/api/shift-notes/unread-count",
                      headers=a).json["unread"] == 0
    assert client.get("/api/shift-notes?unread=1",
                      headers=m).json["total"] == 1


def test_users_and_companies(client):
    m = login(client, "manager")
    new = client.post("/api/users", headers=m, json={"name": "Rose", "username": "rose",
                                                     "password": "5678", "role": "cashier"})
    assert new.status_code == 201
    assert client.post("/api/users", headers=m, json={"name": "R", "username": "rose",
                                                      "password": "5678", "role": "cashier"}).status_code == 409
    client.put(f"/api/users/{new.json['id']}",
               headers=m, json={"is_active": False})
    assert client.post(
        "/api/auth/login", json={"username": "rose", "password": "5678"}).status_code == 403
    me = client.get("/api/auth/me", headers=m).json["id"]
    assert client.put(f"/api/users/{me}", headers=m,
                      json={"role": "cashier"}).status_code == 400

    assert client.post("/api/companies", headers=m,
                       json={"name": "vigo"}).status_code == 409
    assert client.post("/api/companies", headers=m,
                       json={"name": "MoneyGram", "sort_order": 8}).status_code == 201
    c = login(client, "cashier")
    assert client.get("/api/users", headers=c).status_code == 403

