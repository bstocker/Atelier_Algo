"""Acces SQLite : une connexion par requete, refermee en fin de contexte."""

import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g


def now():
    """Horodatage UTC ISO 8601, a la seconde."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=15,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Cree le schema si besoin. Idempotent : sur a chaque demarrage."""
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    schema = os.path.join(os.path.dirname(__file__), "schema.sql")
    conn = sqlite3.connect(app.config["DATABASE"], timeout=15)
    try:
        with open(schema, encoding="utf-8") as fh:
            conn.executescript(fh.read())
        conn.commit()
    finally:
        conn.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
