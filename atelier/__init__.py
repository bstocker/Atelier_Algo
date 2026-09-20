"""Atelier Algo : exercices de motifs en C, sous surveillance, notes sur 20."""

import os

from flask import Flask

from . import db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("ATELIER_SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get(
            "ATELIER_DATABASE", os.path.join(app.instance_path, "atelier.sqlite")
        ),
        ADMIN_USER=os.environ.get("ATELIER_ADMIN_USER", "admin"),
        ADMIN_PASSWORD=os.environ.get("ATELIER_ADMIN_PASSWORD", "atelier"),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)

    if app.config["SECRET_KEY"] == "dev-only-change-me":
        app.logger.warning(
            "ATELIER_SECRET_KEY non defini : les sessions sont signees avec "
            "une cle publique connue. A definir avant toute mise en service."
        )

    db.init_db(app)
    app.teardown_appcontext(db.close_db)

    from . import admin, student
    app.register_blueprint(student.bp)
    app.register_blueprint(admin.bp)

    return app
