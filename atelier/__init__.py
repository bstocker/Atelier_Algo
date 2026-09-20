"""Atelier Algo : exercices de motifs en C, sous surveillance, notes sur 20."""

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db


def load_env_file(path):
    """Charge un fichier .env, sans dependance externe.

    PythonAnywhere n'expose aucune API pour les variables d'environnement :
    le workflow de deploiement depose donc un fichier .env a cote de
    l'application, genere a partir des secrets GitHub du depot.

    Les variables deja presentes dans l'environnement ne sont pas ecrasees.
    Un reglage pose a la main dans l'onglet Web de PythonAnywhere, ou un
    `export` en developpement local, reste donc prioritaire sur le fichier.
    """
    if not os.path.isfile(path):
        return []

    loaded = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name, value = name.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if name and name not in os.environ:
                os.environ[name] = value
                loaded.append(name)
    return loaded


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)

    # Avant toute lecture de os.environ : le fichier depose par le
    # deploiement doit pouvoir alimenter la configuration ci-dessous.
    env_file = os.environ.get(
        "ATELIER_ENV_FILE",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     ".env"),
    )
    loaded = load_env_file(env_file)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("ATELIER_SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get(
            "ATELIER_DATABASE", os.path.join(app.instance_path, "atelier.sqlite")
        ),
        ADMIN_USER=os.environ.get("ATELIER_ADMIN_USER", "admin"),
        ADMIN_PASSWORD=os.environ.get("ATELIER_ADMIN_PASSWORD", "atelier"),
        TRUST_PROXY=os.environ.get("ATELIER_TRUST_PROXY", "1") != "0",
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)

    if loaded:
        app.logger.info("Variables chargees depuis %s : %s",
                        env_file, ", ".join(loaded))

    if app.config["SECRET_KEY"] == "dev-only-change-me":
        app.logger.warning(
            "ATELIER_SECRET_KEY non defini : les sessions sont signees avec "
            "une cle publique connue. A definir avant toute mise en service."
        )

    # PythonAnywhere sert l'application derriere un proxy qui termine le TLS.
    # Sans cela, url_for(..., _external=True) fabriquerait des liens en http,
    # et c'est precisement ce lien que l'enseignant transmet a sa classe.
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_db(app)
    app.teardown_appcontext(db.close_db)

    from . import admin, student
    app.register_blueprint(student.bp)
    app.register_blueprint(admin.bp)

    return app
