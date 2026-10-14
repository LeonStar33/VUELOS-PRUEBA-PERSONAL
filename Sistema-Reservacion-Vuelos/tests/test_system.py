import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from backend.app import create_app
from backend.db import db
from backend import reservas as r


@pytest.fixture
def app(tmp_path):
    clock = [1800000000.0]
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.db"),
            "SECRET_KEY": "test-only",
            "CLOCK": lambda: clock[0],
        }
    )
    app.clock = clock
    return app


def client(app, email="leon@example.test"):
    c = app.test_client()

    def post(url, data):
        token = c.get("/api/session").json["csrf"]
        return c.post(url, json=data, headers={"X-CSRF-Token": token})

    c.post_json = post
    assert (
        post(
            "/api/register",
            {"name": "Equipo", "email": email, "password": "demostracion123"},
        ).status_code
        == 201
    )
    assert (
        post("/api/login", {"email": email, "password": "demostracion123"}).status_code
        == 200
    )
    return c


def booking(c, flight="MX260112", trip="oneway"):
    response = c.post_json("/api/bookings", {"flight": flight, "trip": trip})
    assert response.status_code == 201
    return response.json["id"]


def select(c, b, seat=11, category="adult"):
    return c.post_json(f"/api/bookings/{b}/seats", {"seat": seat, "category": category})


def test_public_catalog_and_capacity(app):
    c = app.test_client()
    flights = c.get("/api/flights").json
    assert len(flights) == 5
    for f in flights:
        assert f["available"] == 30
        seats = c.get(f'/api/flights/{f["id"]}/seats').json
        assert len(seats) == 30
        assert sum(s["cabin"] == "first" for s in seats) == 10
    assert c.get("/").status_code == 200
    assert c.get("/static/app.js").status_code == 200


def test_auth_validation_csrf_and_hash(app):
    c = app.test_client()
    assert c.post("/api/register", json={}).status_code == 403
    c = client(app)
    assert (
        c.post_json(
            "/api/register",
            {"name": "x", "email": "leon@example.test", "password": "12345678"},
        ).status_code
        == 409
    )
    assert (
        c.post_json(
            "/api/login", {"email": "leon@example.test", "password": "wrong"}
        ).status_code
        == 401
    )
    with app.app_context():
        assert (
            db().execute("SELECT password FROM users").fetchone()[0]
            != "demostracion123"
        )
    c.post_json("/api/logout", {})
    assert (
        c.post_json(
            "/api/bookings", {"flight": "MX260112", "trip": "oneway"}
        ).status_code
        == 401
    )


def test_multi_seat_checkout_payment_receipt(app, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    c = client(app)
    b = booking(c, trip="roundtrip")
    assert select(c, b, 11).status_code == 200
    assert select(c, b, 12, "child").status_code == 200
    assert select(c, b, 1, "senior").status_code == 200
    assert c.post_json(f"/api/bookings/{b}/checkout", {}).status_code == 200
    v = c.get("/api/bookings").json["bookings"][0]
    assert v["total"] == (950 + 500 + 8000) * 160
    assert v["expires"] == app.clock[0] + 900
    app.clock[0] += 20
    c.post_json(f"/api/bookings/{b}/checkout", {})
    assert c.get("/api/bookings").json["bookings"][0]["expires"] == v["expires"]
    assert (
        c.post_json(f"/api/bookings/{b}/pay", {"method": "tarjeta"}).json["email"]
        == "no_configurado"
    )
    assert (
        c.post_json(f"/api/bookings/{b}/pay", {"method": "tarjeta"}).json["email"]
        == "ya_procesado"
    )
    result = c.get(f"/api/bookings/{b}/receipt")
    assert (
        result.status_code == 200
        and "MX260112" in result.text
        and "Número de asientos: 3" in result.text
    )
    app.clock[0] += 10000
    assert c.get("/api/flights").json[2]["available"] >= 0
    with app.app_context():
        assert (
            db().execute("SELECT COUNT(*) FROM tickets WHERE active=1").fetchone()[0]
            == 3
        )


@pytest.mark.parametrize(
    "fid,base,discount",
    [
        ("MX261319", 65950, 20),
        ("MX260112", 950, 20),
        ("MX261923", 25950, 0),
        ("MX261512", 30650, 0),
        ("MX260408", 65950, 0),
    ],
)
def test_pricing(app, fid, base, discount):
    with app.app_context():
        f = db().execute("SELECT * FROM flights WHERE id=?", (fid,)).fetchone()
        assert r.price(f, 11, "adult", "oneway") == base * 100
        assert r.price(f, 11, "adult", "roundtrip") == base * 2 * (100 - discount)
        assert r.price(f, 1, "child", "oneway") == f["first"]


@pytest.mark.parametrize("phase,seconds", [("holding", 600), ("checkout", 900)])
def test_expiry_boundary_releases_seats(app, phase, seconds):
    c = client(app)
    b = booking(c)
    select(c, b)
    if phase == "checkout":
        c.post_json(f"/api/bookings/{b}/checkout", {})
    app.clock[0] += seconds
    response = c.post_json(f"/api/bookings/{b}/pay", {"method": "efectivo"})
    assert response.status_code == 409
    assert c.get("/api/bookings").json["bookings"][0]["status"] == "expired"
    b2 = booking(c)
    assert select(c, b2).status_code == 200


def test_selection_does_not_extend_deadline(app):
    c = client(app)
    b = booking(c)
    app.clock[0] += 300
    select(c, b)
    assert c.get("/api/bookings").json["bookings"][0]["expires"] == 1800000600


def test_ownership_and_cancel(app):
    a = client(app)
    b = booking(a)
    select(a, b)
    other = client(app, "vera@example.test")
    for action, data in [
        ("seats", {"seat": 12, "category": "adult"}),
        ("cancel", {}),
        ("checkout", {}),
        ("pay", {"method": "efectivo"}),
    ]:
        assert other.post_json(f"/api/bookings/{b}/{action}", data).status_code == 404
    assert other.get(f"/api/bookings/{b}/receipt").status_code == 404
    assert a.post_json(f"/api/bookings/{b}/cancel", {}).status_code == 200
    b2 = booking(other)
    assert select(other, b2).status_code == 200


def test_race_only_one_winner(app):
    a = client(app)
    b = client(app, "josue@example.test")
    ba = booking(a)
    bb = booking(b)
    barrier = Barrier(2)

    def reserve(uid, bid):
        with app.app_context():
            barrier.wait()
            try:
                r.select(uid, bid, 11, "adult")
                return 200
            except r.Problem as error:
                return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve, 1, ba), pool.submit(reserve, 2, bb)]
        assert sorted(f.result() for f in futures) == [200, 409]
    with app.app_context():
        assert (
            db().execute("SELECT COUNT(*) FROM tickets WHERE active=1").fetchone()[0]
            == 1
        )


def test_invalid_and_empty_checkout(app):
    c = client(app)
    b = booking(c)
    assert c.post_json(f"/api/bookings/{b}/checkout", {}).status_code == 400
    for seat in [0, 31, "11", True]:
        assert select(c, b, seat).status_code == 400
    assert select(c, b, 11, "unknown").status_code == 400
    select(c, b)
    assert (
        c.post_json(f"/api/bookings/{b}/pay", {"method": "efectivo"}).status_code == 409
    )
    c.post_json(f"/api/bookings/{b}/checkout", {})
    assert select(c, b, 12).status_code == 409
    assert (
        c.post_json(f"/api/bookings/{b}/pay", {"method": "bitcoin"}).status_code == 400
    )


def test_smtp_failure_does_not_undo_payment(app, monkeypatch):
    import backend.app as module

    def fail(*args):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(module, "send_receipt", fail)
    c = client(app)
    b = booking(c)
    select(c, b)
    c.post_json(f"/api/bookings/{b}/checkout", {})
    assert (
        c.post_json(f"/api/bookings/{b}/pay", {"method": "efectivo"}).json["email"]
        == "fallo"
    )
    assert c.get(f"/api/bookings/{b}/receipt").status_code == 200


def test_sold_seat_never_reallocated_and_persists(app, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    c = client(app)
    b = booking(c)
    select(c, b)
    c.post_json(f"/api/bookings/{b}/checkout", {})
    c.post_json(f"/api/bookings/{b}/pay", {"method": "efectivo"})
    app.clock[0] += 100000
    c2 = client(app, "second@example.test")
    b2 = booking(c2)
    assert select(c2, b2).status_code == 409
    assert c.post_json(f"/api/bookings/{b}/cancel", {}).status_code == 409
    reopened = create_app(
        {"TESTING": True, "DATABASE": app.config["DATABASE"], "SECRET_KEY": "test-only"}
    )
    with reopened.app_context():
        assert (
            db().execute("SELECT status FROM bookings WHERE id=?", (b,)).fetchone()[0]
            == "paid"
        )
        assert db().execute("SELECT COUNT(*) FROM flights").fetchone()[0] == 5


def test_remove_and_reselect(app):
    c = client(app)
    b = booking(c)
    select(c, b)
    assert (
        c.post_json(
            f"/api/bookings/{b}/seats",
            {"seat": 11, "category": "adult", "remove": True},
        ).status_code
        == 200
    )
    assert c.get("/api/bookings").json["bookings"][0]["tickets"] == []
    assert select(c, b, 11, "senior").status_code == 200


def test_smtp_composition_with_fake_transport(app, monkeypatch):
    from backend.comprobantes import send_receipt

    monkeypatch.delenv("SMTP_HOST", raising=False)
    c = client(app)
    b = booking(c)
    select(c, b)
    c.post_json(f"/api/bookings/{b}/checkout", {})
    c.post_json(f"/api/bookings/{b}/pay", {"method": "efectivo"})
    calls = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, context):
            calls.append("tls")

        def send_message(self, message):
            assert message["To"] == "leon@example.test"
            assert len(list(message.iter_attachments())) == 1
            calls.append("sent")

    monkeypatch.setenv("SMTP_HOST", "example.test")
    monkeypatch.setenv("SMTP_FROM", "sender@example.test")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.setattr("backend.comprobantes.smtplib.SMTP", FakeSMTP)
    with app.app_context():
        assert send_receipt(b, 1) == "enviado"
    assert calls == ["tls", "sent"]
