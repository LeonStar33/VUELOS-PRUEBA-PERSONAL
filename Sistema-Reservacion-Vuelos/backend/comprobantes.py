import os, smtplib, ssl
from email.message import EmailMessage
from datetime import datetime, timezone
from .db import db
from .reservas import Problem

LABELS = {"adult": "Adulto", "child": "Niño", "senior": "Tercera edad"}


def receipt(bid, uid):
    c = db()
    b = c.execute(
        "SELECT b.*,u.name,u.email,f.destination,f.departure FROM bookings b JOIN users u ON u.id=b.user_id JOIN flights f ON f.id=b.flight_id WHERE b.id=? AND b.user_id=? AND b.status='paid'",
        (bid, uid),
    ).fetchone()
    if not b:
        raise Problem("Comprobante no disponible.", 404)
    ts = c.execute(
        "SELECT * FROM tickets WHERE booking_id=? ORDER BY seat", (bid,)
    ).fetchall()
    lines = [
        "SISTEMA DE RESERVACIÓN DE VUELOS",
        "COMPROBANTE DE SIMULACIÓN — SIN VALIDEZ PARA VIAJAR",
        f"Folio: {bid}",
        f'Usuario: {b["name"]}',
        f'Vuelo: {b["flight_id"]}',
        "Origen: Ciudad de México",
        f'Destino: {b["destination"]}',
        f'Salida: {b["departure"]}',
        "Terminal 2 · Puerta 2",
        f'Tipo: {"Sencillo" if b["trip"]=="oneway" else "Ida y vuelta (retorno pendiente de itinerario)"}',
        f"Número de asientos: {len(ts)}",
    ]
    for t in ts:
        lines.append(
            f'Asiento {t["seat"]} | {"Primera" if t["seat"]<=10 else "Turista"} | {LABELS[t["category"]]} | ${t["amount"]/100:,.2f} MXN'
        )
    lines += [
        f'Total: ${b["total"]/100:,.2f} MXN',
        f'Método simulado: {b["method"]}',
        f'Confirmación UTC: {datetime.fromtimestamp(b["paid_at"],timezone.utc).isoformat()}',
        "No se ha asignado asiento ni fecha de regreso. No se efectuó ningún cobro.",
    ]
    return "\n".join(lines), b["email"]


def send_receipt(bid, uid):
    if not os.getenv("SMTP_HOST"):
        return "no_configurado"
    body, address = receipt(bid, uid)
    message = EmailMessage()
    message["Subject"] = "Comprobante de compra simulada"
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = address
    message.set_content(body)
    message.add_attachment(
        body.encode("utf-8"),
        maintype="text",
        subtype="plain",
        filename=f"comprobante-{bid}.txt",
    )
    with smtplib.SMTP(
        os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=8
    ) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)
    return "enviado"
