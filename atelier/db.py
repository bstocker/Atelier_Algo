"""Acces SQLite : une connexion par requete, refermee en fin de contexte."""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import current_app, g


def now():
    """Horodatage UTC ISO 8601, a la seconde."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ago(seconds):
    """Le meme horodatage, mais d'il y a `seconds` secondes.

    Sert aux ecritures conditionnelles : comparer deux horodatages comme
    du texte est correct tant qu'ils sortent tous les deux d'ici — meme
    format, meme fuseau.
    """
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)) \
        .replace(microsecond=0).isoformat()


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


# Colonnes ajoutees apres la premiere mise en service. `CREATE TABLE IF NOT
# EXISTS` laisse intactes les tables deja presentes : sans ce rattrapage,
# une base deployee avant l'ajout n'aurait jamais la colonne.
ADDED_COLUMNS = (
    ("task", "wrong_attempts", "INTEGER NOT NULL DEFAULT 0"),
    ("session", "exam_mode", "INTEGER NOT NULL DEFAULT 0"),
    ("session", "created_by", "TEXT NOT NULL DEFAULT ''"),
)


def _catch_up(conn):
    """Ajoute les colonnes manquantes d'une base deja en place. Idempotent."""
    for table, column, declaration in ADDED_COLUMNS:
        present = {row[1] for row in
                   conn.execute("PRAGMA table_info(%s)" % table)}
        if column not in present:
            conn.execute("ALTER TABLE %s ADD COLUMN %s %s"
                         % (table, column, declaration))


def init_db(app):
    """Cree le schema si besoin. Idempotent : sur a chaque demarrage.

    C'est aussi ce passage qui fait basculer une base deja en place hors
    du mode WAL : le `PRAGMA` de `schema.sql` s'applique au fichier, pas
    a la connexion. La bascule echoue sans bruit si un autre processus
    tient la base ouverte — SQLite rend alors le mode courant au lieu de
    lever une erreur — d'ou la relecture et l'avertissement.
    """
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    schema = os.path.join(os.path.dirname(__file__), "schema.sql")
    conn = sqlite3.connect(app.config["DATABASE"], timeout=15)
    try:
        with open(schema, encoding="utf-8") as fh:
            conn.executescript(fh.read())
        _catch_up(conn)
        conn.commit()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()

    if mode.lower() == "wal":
        app.logger.warning(
            "La base est en mode WAL alors que le schema demande DELETE. "
            "Sur un disque monte par le reseau, ce mode expose la base a "
            "la corruption. Arreter l'application, verifier qu'aucun "
            "processus ne la tient ouverte, puis relancer."
        )


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
