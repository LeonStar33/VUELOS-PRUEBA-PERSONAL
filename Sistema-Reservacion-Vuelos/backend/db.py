import sqlite3, json
from pathlib import Path
from flask import current_app, g

ROOT = Path(__file__).resolve().parents[1]


def db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"], timeout=10, isolation_level=None
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def initialize(app):
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        c = db()
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript((ROOT / "database/schema.sql").read_text())
        c.execute("BEGIN IMMEDIATE")
        try:
            for f in json.loads((ROOT / "database/flights.json").read_text()):
                c.execute(
                    "INSERT OR IGNORE INTO flights VALUES (?,?,?,?,?,?,?,?,?)",
                    tuple(f.values()),
                )
                for n in range(1, 31):
                    c.execute(
                        "INSERT OR IGNORE INTO seats VALUES (?,?,?)",
                        (f["id"], n, "first" if n <= 10 else "tourist"),
                    )
            c.commit()
        except Exception:
            c.rollback()
            raise

    @app.teardown_appcontext
    def close(error):
        c = g.pop("db", None)
        if c:
            c.close()
