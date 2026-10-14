import time, uuid
from contextlib import contextmanager
from flask import current_app
from .db import db


class Problem(Exception):
    def __init__(self, message, status=400):
        self.message = message
        self.status = status


def now():
    return current_app.config.get("CLOCK", time.time)()


def expire(c):
    c.execute(
        "UPDATE bookings SET status='expired' WHERE status IN ('holding','checkout') AND expires<=?",
        (now(),),
    )
    c.execute(
        "UPDATE tickets SET active=0 WHERE active=1 AND booking_id IN (SELECT id FROM bookings WHERE status IN ('expired','cancelled'))"
    )


@contextmanager
def transaction():
    c = db()
    c.execute("BEGIN IMMEDIATE")
    try:
        expire(c)
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise


def owned(c, bid, uid):
    b = c.execute(
        "SELECT * FROM bookings WHERE id=? AND user_id=?", (bid, uid)
    ).fetchone()
    if not b:
        raise Problem("Reserva no encontrada.", 404)
    return b


def price(f, seat, category, trip):
    base = f["first"] if seat <= 10 else f[category]
    # Demo: dos trayectos; descuento sobre cada tarifa sencilla.
    return base if trip == "oneway" else base * 2 * (100 - f["discount"]) // 100


def start(uid, flight, trip):
    if trip not in ("oneway", "roundtrip"):
        raise Problem("Tipo de viaje inválido.")
    with transaction() as c:
        if not c.execute("SELECT id FROM flights WHERE id=?", (flight,)).fetchone():
            raise Problem("Vuelo no encontrado.", 404)
        if (
            c.execute(
                "SELECT COUNT(*) FROM bookings WHERE user_id=? AND status IN ('holding','checkout')",
                (uid,),
            ).fetchone()[0]
            >= 3
        ):
            raise Problem("Finaliza o cancela tus reservas abiertas.")
        bid = uuid.uuid4().hex
        c.execute(
            "INSERT INTO bookings(id,user_id,flight_id,trip,status,expires,created) VALUES (?,?,?,?,'holding',?,?)",
            (bid, uid, flight, trip, now() + 600, now()),
        )
    return bid


def select(uid, bid, seat, category, remove=False):
    if (
        type(seat) is not int
        or not 1 <= seat <= 30
        or category not in ("adult", "child", "senior")
    ):
        raise Problem("Asiento o categoría inválidos.")
    with transaction() as c:
        b = owned(c, bid, uid)
        if b["status"] != "holding":
            raise Problem("La selección terminó o la reserva venció.", 409)
        if remove:
            c.execute("DELETE FROM tickets WHERE booking_id=? AND seat=?", (bid, seat))
            return
        other = c.execute(
            "SELECT booking_id FROM tickets WHERE flight_id=? AND seat=? AND active=1",
            (b["flight_id"], seat),
        ).fetchone()
        if other and other[0] != bid:
            raise Problem("Otro usuario ya reservó ese asiento.", 409)
        f = c.execute("SELECT * FROM flights WHERE id=?", (b["flight_id"],)).fetchone()
        c.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,1) ON CONFLICT(booking_id,seat) DO UPDATE SET category=excluded.category,amount=excluded.amount",
            (bid, b["flight_id"], seat, category, price(f, seat, category, b["trip"])),
        )


def checkout(uid, bid):
    with transaction() as c:
        b = owned(c, bid, uid)
        if b["status"] == "checkout":
            return
        if b["status"] != "holding":
            raise Problem("La reserva ya no está disponible.", 409)
        total = c.execute(
            "SELECT SUM(amount) FROM tickets WHERE booking_id=? AND active=1", (bid,)
        ).fetchone()[0]
        if total is None:
            raise Problem("Selecciona al menos un asiento.")
        c.execute(
            "UPDATE bookings SET status='checkout',expires=?,total=? WHERE id=?",
            (now() + 900, total, bid),
        )


def pay(uid, bid, method):
    if method not in ("efectivo", "tarjeta"):
        raise Problem("Método inválido.")
    with transaction() as c:
        b = owned(c, bid, uid)
        if b["status"] == "paid":
            return False
        if b["status"] != "checkout":
            raise Problem("La compra venció o no ha comenzado.", 409)
        c.execute(
            "UPDATE bookings SET status='paid',method=?,paid_at=? WHERE id=?",
            (method, now(), bid),
        )
    return True


def cancel(uid, bid):
    with transaction() as c:
        b = owned(c, bid, uid)
        if b["status"] == "paid":
            raise Problem("No se cancelan compras confirmadas en esta demo.", 409)
        c.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (bid,))
        c.execute("UPDATE tickets SET active=0 WHERE booking_id=?", (bid,))
