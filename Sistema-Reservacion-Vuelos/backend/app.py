import os, secrets, sqlite3, re
from pathlib import Path
from functools import wraps
from flask import Flask, request, session, jsonify, render_template, Response
from werkzeug.security import generate_password_hash, check_password_hash
from .db import db, initialize, ROOT
from . import reservas as r
from .comprobantes import receipt, send_receipt


def create_app(config=None):
    app = Flask(
        __name__,
        template_folder=str(ROOT / "frontend/templates"),
        static_folder=str(ROOT / "frontend/static"),
    )
    instance = ROOT / "instance"
    instance.mkdir(exist_ok=True)
    secret = instance / "secret.key"
    if not secret.exists():
        try:
            with secret.open("x") as f:
                f.write(secrets.token_hex(32))
            secret.chmod(0o600)
        except FileExistsError:
            pass
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or secret.read_text(),
        DATABASE=str(instance / "vuelos.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=16384,
    )
    if config:
        app.config.update(config)
    initialize(app)

    def login_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get("uid"):
                raise r.Problem("Inicia sesión para reservar.", 401)
            return fn(*args, **kwargs)

        return wrapped

    @app.before_request
    def csrf():
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            token = request.headers.get("X-CSRF-Token", "")
            if not token or not secrets.compare_digest(token, session.get("csrf", "")):
                raise r.Problem("Recarga la página e inténtalo de nuevo.", 403)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(r.Problem)
    def problem(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(sqlite3.OperationalError)
    def busy(e):
        app.logger.exception("Database operation failed")
        return jsonify(error="Base de datos ocupada. Intenta nuevamente."), 503

    def data():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise r.Problem("Se requiere un objeto JSON.")
        return value

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/api/session")
    def state():
        session.setdefault("csrf", secrets.token_hex(24))
        u = (
            db()
            .execute(
                "SELECT id,name,email FROM users WHERE id=?", (session.get("uid"),)
            )
            .fetchone()
        )
        return jsonify(user=dict(u) if u else None, csrf=session["csrf"], now=r.now())

    @app.post("/api/register")
    def register():
        d = data()
        name = d.get("name", "")
        email = d.get("email", "")
        password = d.get("password", "")
        if not all(isinstance(x, str) for x in (name, email, password)):
            raise r.Problem("Datos inválidos.")
        name = name.strip()
        email = email.strip().lower()
        if (
            not 1 <= len(name) <= 80
            or len(email) > 254
            or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
            or not 8 <= len(password) <= 128
        ):
            raise r.Problem(
                "Indica nombre, correo válido y contraseña de 8 a 128 caracteres."
            )
        try:
            db().execute(
                "INSERT INTO users(name,email,password) VALUES (?,?,?)",
                (name, email, generate_password_hash(password)),
            )
        except sqlite3.IntegrityError:
            raise r.Problem("Ese correo ya está registrado.", 409)
        return jsonify(ok=True), 201

    @app.post("/api/login")
    def login():
        d = data()
        email = d.get("email", "")
        password = d.get("password", "")
        if not isinstance(email, str) or not isinstance(password, str):
            raise r.Problem("Datos inválidos.")
        u = (
            db()
            .execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),))
            .fetchone()
        )
        if not u or not check_password_hash(u["password"], password):
            raise r.Problem("Correo o contraseña incorrectos.", 401)
        session.clear()
        session["uid"] = u["id"]
        session["csrf"] = secrets.token_hex(24)
        return jsonify(ok=True)

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/flights")
    def flights():
        with r.transaction() as c:
            rows = c.execute(
                "SELECT f.*,30-(SELECT COUNT(*) FROM tickets t WHERE t.flight_id=f.id AND t.active=1) available FROM flights f ORDER BY departure"
            ).fetchall()
        return jsonify([dict(x) for x in rows])

    @app.get("/api/flights/<fid>/seats")
    def seats(fid):
        with r.transaction() as c:
            rows = c.execute(
                "SELECT s.number,s.cabin,b.user_id,b.id bid,b.status FROM seats s LEFT JOIN tickets t ON t.flight_id=s.flight_id AND t.seat=s.number AND t.active=1 LEFT JOIN bookings b ON b.id=t.booking_id WHERE s.flight_id=? ORDER BY s.number",
                (fid,),
            ).fetchall()
            result = [
                dict(
                    number=x["number"],
                    cabin=x["cabin"],
                    state=(
                        "available"
                        if not x["bid"]
                        else ("paid" if x["status"] == "paid" else "held")
                    ),
                    mine=x["user_id"] == session.get("uid") and x["bid"] is not None,
                )
                for x in rows
            ]
        return jsonify(result)

    @app.post("/api/bookings")
    @login_required
    def start():
        d = data()
        if not isinstance(d.get("flight"), str):
            raise r.Problem("Vuelo inválido.")
        return jsonify(id=r.start(session["uid"], d["flight"], d.get("trip"))), 201

    @app.get("/api/bookings")
    @login_required
    def bookings():
        with r.transaction() as c:
            rows = c.execute(
                "SELECT b.*,f.destination FROM bookings b JOIN flights f ON f.id=b.flight_id WHERE user_id=? ORDER BY created DESC",
                (session["uid"],),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["tickets"] = [
                    dict(t)
                    for t in c.execute(
                        "SELECT seat,category,amount FROM tickets WHERE booking_id=? ORDER BY seat",
                        (row["id"],),
                    )
                ]
                result.append(item)
        return jsonify(bookings=result, now=r.now())

    @app.post("/api/bookings/<bid>/seats")
    @login_required
    def select(bid):
        d = data()
        r.select(
            session["uid"],
            bid,
            d.get("seat"),
            d.get("category"),
            d.get("remove") is True,
        )
        return jsonify(ok=True)

    @app.post("/api/bookings/<bid>/checkout")
    @login_required
    def checkout(bid):
        r.checkout(session["uid"], bid)
        return jsonify(ok=True)

    @app.post("/api/bookings/<bid>/cancel")
    @login_required
    def cancel(bid):
        r.cancel(session["uid"], bid)
        return jsonify(ok=True)

    @app.post("/api/bookings/<bid>/pay")
    @login_required
    def pay(bid):
        fresh = r.pay(session["uid"], bid, data().get("method"))
        mail = "ya_procesado"
        if fresh:
            try:
                mail = send_receipt(bid, session["uid"])
            except Exception:
                mail = "fallo"
                app.logger.warning("No se pudo enviar comprobante; compra conservada.")
        return jsonify(ok=True, email=mail)

    @app.get("/api/bookings/<bid>/receipt")
    @login_required
    def download(bid):
        body, _ = receipt(bid, session["uid"])
        return Response(
            body,
            content_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="comprobante-{bid}.txt"'
            },
        )

    return app
