"""Comptes de l'espace enseignant : l'administrateur, et les profils qu'il crée.

Deux sortes de comptes, et une seule différence entre elles.

L'**administrateur** vient des variables d'environnement
(`ATELIER_ADMIN_USER` / `ATELIER_ADMIN_PASSWORD`). Il n'est pas dans la
base : c'est le compte de secours, celui qui existe avant qu'aucune table
ne soit remplie. Lui seul gère les comptes.

Un **profil enseignant** vit dans la table `teacher`. Il crée des sessions,
les lance, suit les copies en direct, exporte les notes, importe des QCM —
tout l'espace enseignant, sauf la page des comptes. Il ne peut donc pas
créer de profil, ni réinitialiser le mot de passe d'un autre, ni se
supprimer un concurrent : la gestion des comptes reste à l'administrateur.

Les mots de passe ne sont jamais stockés en clair : `werkzeug.security` les
hache (scrypt par défaut) et les vérifie.
"""

import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from .db import execute, now, query

# Un mot de passe dicté à un collègue à l'oral ; huit caractères est le
# minimum qui reste honnête sans devenir impraticable.
MIN_PASSWORD = 8
MAX_USERNAME = 40


class BadAccount(Exception):
    """Demande refusée. Le message est montré tel quel à l'administrateur."""


def clean_username(raw):
    return " ".join(str(raw or "").split())[:MAX_USERNAME]


def _check_password(password):
    if len(password or "") < MIN_PASSWORD:
        raise BadAccount("Le mot de passe doit faire au moins %d caractères."
                         % MIN_PASSWORD)


def _same(left, right):
    """Comparaison a temps constant, tolerante aux accents.

    `secrets.compare_digest` refuse les chaines non ASCII : un identifiant
    accentue saisi au clavier ferait une erreur 500. On compare donc les
    octets.
    """
    return secrets.compare_digest(str(left or "").encode("utf-8"),
                                  str(right or "").encode("utf-8"))


def is_root(app_config, username):
    """Vrai si ce nom est celui du compte administrateur."""
    return _same(clean_username(username).lower(),
                 app_config["ADMIN_USER"].lower())


def verify(app_config, username, password):
    """Identifie un compte. Rend (nom, administrateur ?) ou None.

    L'administrateur est essayé d'abord : son mot de passe vient de
    l'environnement, et aucun profil ne peut porter son nom (cf. `create`).
    """
    username = clean_username(username)
    password = password or ""
    if not username:
        return None

    # compare_digest sur les deux champs, et sans court-circuit : le temps de
    # reponse ne doit pas dire si l'identifiant existe.
    root_ok = (_same(username, app_config["ADMIN_USER"])
               & _same(password, app_config["ADMIN_PASSWORD"]))
    if root_ok:
        return username, True

    row = query("SELECT * FROM teacher WHERE username = ?", (username,),
                one=True)
    if row is None or not check_password_hash(row["password_hash"], password):
        return None
    execute("UPDATE teacher SET last_login_at = ? WHERE id = ?",
            (now(), row["id"]))
    return row["username"], False


def create(app_config, username, password, created_by):
    """Ajoute un profil enseignant. Rend son nom."""
    username = clean_username(username)
    if not username:
        raise BadAccount("L'identifiant est obligatoire.")
    _check_password(password)
    if is_root(app_config, username):
        raise BadAccount("Cet identifiant est celui du compte administrateur.")
    if query("SELECT 1 FROM teacher WHERE username = ?", (username,),
             one=True) is not None:
        raise BadAccount("Un compte porte déjà l'identifiant « %s »."
                         % username)
    execute(
        """INSERT INTO teacher (username, password_hash, created_by, created_at)
           VALUES (?, ?, ?, ?)""",
        (username, generate_password_hash(password), created_by, now()),
    )
    return username


def set_password(teacher_id, password):
    """Réinitialise le mot de passe d'un profil. Rend son nom."""
    _check_password(password)
    row = query("SELECT * FROM teacher WHERE id = ?", (teacher_id,), one=True)
    if row is None:
        raise BadAccount("Compte introuvable.")
    execute("UPDATE teacher SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), teacher_id))
    return row["username"]


def delete(teacher_id):
    """Supprime un profil. Rend son nom, ou None s'il n'existait pas.

    Les sessions qu'il a créées restent : elles portent les copies des
    élèves, et l'historique de la classe ne dépend pas de qui a cliqué.
    """
    row = query("SELECT * FROM teacher WHERE id = ?", (teacher_id,), one=True)
    if row is None:
        return None
    execute("DELETE FROM teacher WHERE id = ?", (teacher_id,))
    return row["username"]


def listing():
    """Les profils enseignants, du plus récent au plus ancien."""
    return query("SELECT * FROM teacher ORDER BY created_at DESC, id DESC")
