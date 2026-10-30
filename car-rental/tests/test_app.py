"""My automated tests for the Sprint 1 stories.

Each test checks one acceptance criterion from the product backlog.
"""
from datetime import date, timedelta

import pytest

from app import create_app

TOKEN = "test-token"
GOOD = dict(full_name="Test User", email="test@example.com", phone="5195551234",
            licence_no="A1234-56789", password="Passw0rd1", confirm="Passw0rd1", consent="on")


# every test gets a brand new app and an empty temporary database
@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "t.db")})
    c = app.test_client()
    with c.session_transaction() as s:
        s["_csrf"] = TOKEN  # put a known CSRF token in the session so my posts are accepted
    return c


# helper: sends a form post with the CSRF token filled in
def post(c, url, **data):
    data["_csrf"] = TOKEN
    return c.post(url, data=data, follow_redirects=False)


def register(c, **over):
    return post(c, "/register", **{**GOOD, **over})


def login(c, email="test@example.com", password="Passw0rd1"):
    r = post(c, "/login", email=email, password=password)
    with c.session_transaction() as s:  # keep the CSRF token after session.clear()
        s["_csrf"] = TOKEN
    return r


# helper: a date N days from today as YYYY-MM-DD
def iso(days):
    return (date.today() + timedelta(days=days)).isoformat()


# ---------- UI-1 Create Account ----------
def test_register_success_redirects_to_login(client):
    r = register(client)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_register_stores_hash_not_plain_password(client):
    register(client)
    import sqlite3
    row = sqlite3.connect(client.application.config["DATABASE"]).execute(
        "SELECT password_hash FROM users WHERE email='test@example.com'").fetchone()
    assert row[0] != "Passw0rd1" and len(row[0]) > 30


def test_register_duplicate_email_rejected(client):
    register(client)
    r = register(client)
    assert r.status_code == 200 and b"already exists" in r.data


@pytest.mark.parametrize("field,value,msg", [
    ("full_name", "", b"full name"),
    ("email", "not-an-email", b"valid email"),
    ("phone", "123", b"10 digits"),
    ("licence_no", "x", b"licence number"),
    ("password", "short1", b"8 characters"),
    ("confirm", "Different1", b"do not match"),
    ("consent", "", b"agree"),
])
def test_register_validation_errors(client, field, value, msg):
    data = {**GOOD, field: value}
    if field == "password":
        data["confirm"] = value
    if field == "consent":
        data.pop("consent")
    r = post(client, "/register", **data)
    assert r.status_code == 200 and msg in r.data


def test_register_requires_csrf_token(client):
    r = client.post("/register", data=GOOD)
    assert r.status_code == 400


# ---------- UI-6 Log In ----------
def test_login_success_goes_to_search(client):
    register(client)
    r = login(client)
    assert r.status_code == 302 and "/search" in r.headers["Location"]


def test_login_wrong_password_shows_error(client):
    register(client)
    r = login(client, password="wrong")
    assert r.status_code == 200 and b"Incorrect email or password" in r.data


def test_login_unknown_email_same_message(client):
    r = login(client, email="nobody@example.com")
    assert b"Incorrect email or password" in r.data


def test_account_locks_after_three_failures(client):
    register(client)
    for _ in range(3):
        login(client, password="wrong")
    r = login(client)  # correct password, but locked
    assert b"Too many failed attempts" in r.data


def test_logout_ends_session(client):
    register(client)
    login(client)
    post(client, "/logout")
    r = client.get("/search")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_session_cookie_has_inactivity_lifetime(client):
    assert client.application.config["PERMANENT_SESSION_LIFETIME"].total_seconds() == 15 * 60


# ---------- ADM-2 Manager Access ----------
def test_manager_can_open_manager_page(client):
    r = login(client, "manager@carrental.com", "Manager123!")
    assert "/manager" in r.headers["Location"]
    assert client.get("/manager").status_code == 200


def test_customer_blocked_from_manager_page(client):
    register(client)
    login(client)
    assert client.get("/manager").status_code == 403


def test_anonymous_redirected_from_manager_page(client):
    r = client.get("/manager")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


# ---------- UI-2 Search Cars ----------
def search(c, car_type, pickup, ret):
    return c.get("/search", query_string={"car_type": car_type, "pickup": pickup, "return": ret})


def test_search_requires_login(client):
    assert search(client, "SUV", iso(1), iso(2)).status_code == 302


def test_search_returns_only_requested_type(client):
    register(client); login(client)
    r = search(client, "Sedan", iso(20), iso(22))
    assert b"Civic" in r.data and b"RAV4" not in r.data


def test_search_excludes_booked_car_on_overlap(client):
    register(client); login(client)
    # the seed data books RAV4 (car 1) from day 3 to day 6, so these dates overlap it
    r = search(client, "SUV", iso(5), iso(8))
    assert b"RAV4" not in r.data and b"CR-V" in r.data


def test_search_includes_car_when_no_overlap(client):
    register(client); login(client)
    r = search(client, "SUV", iso(10), iso(12))
    assert b"RAV4" in r.data


def test_search_no_results_message(client):
    register(client); login(client)
    # there is only one truck, so I book it directly in the database first
    import sqlite3
    db = sqlite3.connect(client.application.config["DATABASE"])
    db.execute("INSERT INTO reservations (user_id,car_id,start_date,end_date) VALUES (1,9,?,?)",
               (iso(30), iso(35)))
    db.commit()
    r = search(client, "Truck", iso(31), iso(32))
    assert b"No cars are available for those dates" in r.data


def test_search_rejects_return_before_pickup(client):
    register(client); login(client)
    r = search(client, "SUV", iso(5), iso(3))
    assert b"on or after the pickup date" in r.data


def test_search_rejects_past_pickup(client):
    register(client); login(client)
    r = search(client, "SUV", iso(-2), iso(3))
    assert b"cannot be in the past" in r.data


def test_search_sql_injection_is_harmless(client):
    register(client); login(client)
    r = search(client, "SUV' OR '1'='1", iso(1), iso(2))
    assert r.status_code == 200 and b"Choose a car type" in r.data
