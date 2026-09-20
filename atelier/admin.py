"""Espace enseignant : lancement des sessions, suivi direct, historique."""

import csv
import functools
import io
import json
import random
import secrets

from flask import (Blueprint, Response, abort, jsonify, redirect,
                   render_template, request, session, url_for)

from . import exercises as ex
from . import scoring
from .db import execute, get_db, now, query

bp = Blueprint("admin", __name__, url_prefix="/admin")

# Alphabet sans O/0 ni I/1 : un code dicte a l'oral reste lisible.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def require_admin(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/admin/api/"):
                abort(401, description="Session enseignant expirée.")
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def new_code():
    for _ in range(50):
        code = "".join(random.choice(CODE_ALPHABET) for _ in range(6))
        if query("SELECT 1 FROM session WHERE code = ?", (code,), one=True) is None:
            return code
    raise RuntimeError("Impossible de generer un code de session libre.")


# --------------------------------------------------------------------------
# Authentification
# --------------------------------------------------------------------------

@bp.route("/login", methods=("GET", "POST"))
def login():
    from flask import current_app
    error = None
    if request.method == "POST":
        user = request.form.get("username", "")
        password = request.form.get("password", "")
        ok = (secrets.compare_digest(user, current_app.config["ADMIN_USER"])
              & secrets.compare_digest(password,
                                       current_app.config["ADMIN_PASSWORD"]))
        if ok:
            session["is_admin"] = True
            target = request.args.get("next", "")
            return redirect(target if target.startswith("/admin")
                            else url_for("admin.dashboard"))
        error = "Identifiants incorrects."
    return render_template("admin_login.html", error=error)


@bp.post("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin.login"))


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

@bp.get("/")
@require_admin
def dashboard():
    sessions = query(
        """SELECT x.*, COUNT(s.id) AS students
             FROM session x LEFT JOIN student s ON s.session_id = x.id
            WHERE x.status IN ('draft', 'open')
            GROUP BY x.id ORDER BY x.created_at DESC""",
    )
    return render_template(
        "admin_dashboard.html", sessions=sessions,
        patterns=[ex.PATTERNS[k] for k in ex.ALL_KEYS],
    )


@bp.post("/sessions")
@require_admin
def create_session():
    title = " ".join(request.form.get("title", "").split())[:120] \
        or "Session sans titre"
    keys = [k for k in request.form.getlist("patterns") if k in ex.PATTERNS]
    if not keys:
        keys = list(ex.ALL_KEYS)
    keys.sort(key=ex.ALL_KEYS.index)

    session_id = execute(
        """INSERT INTO session (code, title, patterns, status, created_at)
           VALUES (?, ?, ?, 'draft', ?)""",
        (new_code(), title, json.dumps(keys), now()),
    )
    return redirect(url_for("admin.session_view", session_id=session_id))


@bp.post("/sessions/<int:session_id>/open")
@require_admin
def open_session(session_id):
    execute(
        """UPDATE session SET status = 'open', opened_at = ?
            WHERE id = ? AND status = 'draft'""",
        (now(), session_id),
    )
    return redirect(url_for("admin.session_view", session_id=session_id))


@bp.post("/sessions/<int:session_id>/close")
@require_admin
def close_session(session_id):
    """Cloture la session et fige la note sur 20 de chaque etudiant."""
    room = query("SELECT * FROM session WHERE id = ?", (session_id,), one=True)
    if room is None:
        abort(404)
    if room["status"] == "closed":
        return redirect(url_for("admin.session_view", session_id=session_id))

    total = len(json.loads(room["patterns"]))
    db = get_db()
    stamp = now()
    for student in query("SELECT * FROM student WHERE session_id = ?",
                         (session_id,)):
        solved = query(
            "SELECT COUNT(*) AS c FROM task WHERE student_id = ? AND solved = 1",
            (student["id"],), one=True,
        )["c"]
        score = scoring.final_score(solved, total, student["penalty_points"])
        db.execute(
            """UPDATE student
                  SET final_score = ?, finished_at = COALESCE(finished_at, ?)
                WHERE id = ?""",
            (score, stamp, student["id"]),
        )
    db.execute("UPDATE session SET status = 'closed', closed_at = ? WHERE id = ?",
               (stamp, session_id))
    db.commit()
    return redirect(url_for("admin.session_view", session_id=session_id))


@bp.get("/sessions/<int:session_id>")
@require_admin
def session_view(session_id):
    room = query("SELECT * FROM session WHERE id = ?", (session_id,), one=True)
    if room is None:
        abort(404)
    keys = json.loads(room["patterns"])
    return render_template(
        "admin_session.html", room=room,
        pattern_names=[ex.PATTERNS[k].name for k in keys],
        join_url=url_for("student.join_form", _external=True),
    )


# --------------------------------------------------------------------------
# Suivi direct
# --------------------------------------------------------------------------

def _live_payload(session_id):
    room = query("SELECT * FROM session WHERE id = ?", (session_id,), one=True)
    if room is None:
        abort(404)
    keys = json.loads(room["patterns"])
    total = len(keys)

    # Cette vue est interrogee toutes les 3 secondes : on lit toutes les
    # copies en deux requetes, pas en une par etudiant.
    students = query(
        """SELECT * FROM student WHERE session_id = ?
            ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE""",
        (session_id,),
    )
    by_student = {s["id"]: {} for s in students}
    for task in query(
        """SELECT t.* FROM task t JOIN student s ON s.id = t.student_id
            WHERE s.session_id = ?""",
        (session_id,),
    ):
        by_student[task["student_id"]][task["pattern_key"]] = task

    rows = []
    for student in students:
        tasks = by_student[student["id"]]
        solved = sum(1 for t in tasks.values() if t["solved"])
        live = scoring.final_score(solved, total, student["penalty_points"])
        rows.append({
            "id": student["id"],
            "name": "%s %s" % (student["last_name"].upper(),
                               student["first_name"]),
            "solved": solved,
            "total": total,
            "attempts": sum(t["attempts"] for t in tasks.values()),
            "exits": student["exit_count"],
            "penalty": student["penalty_points"],
            "score": student["final_score"] if student["final_score"] is not None
                     else live,
            "finished": bool(student["finished_at"]),
            "last_seen": student["last_seen_at"],
            "cells": [
                {"key": k,
                 "solved": bool(tasks[k]["solved"]) if k in tasks else False,
                 "attempts": tasks[k]["attempts"] if k in tasks else 0}
                for k in keys
            ],
        })

    scores = [r["score"] for r in rows]
    return {
        "status": room["status"],
        "code": room["code"],
        "title": room["title"],
        "patterns": [{"key": k, "name": ex.PATTERNS[k].name} for k in keys],
        "students": rows,
        "stats": {
            "count": len(rows),
            "finished": sum(1 for r in rows if r["finished"]),
            "average": round(sum(scores) / len(scores), 2) if scores else None,
            "exits": sum(r["exits"] for r in rows),
        },
        "server_time": now(),
    }


@bp.get("/api/sessions/<int:session_id>/live")
@require_admin
def api_live(session_id):
    return jsonify(_live_payload(session_id))


@bp.get("/sessions/<int:session_id>/export.csv")
@require_admin
def export_csv(session_id):
    data = _live_payload(session_id)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Nom", "Motifs reussis", "Total motifs", "Tentatives",
                     "Sorties", "Penalite", "Note sur 20", "Termine"])
    for row in data["students"]:
        writer.writerow([row["name"], row["solved"], row["total"],
                         row["attempts"], row["exits"], row["penalty"],
                         ("%.2f" % row["score"]).replace(".", ","),
                         "oui" if row["finished"] else "non"])
    return Response(
        buf.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="session-%s.csv"' % data["code"]},
    )


# --------------------------------------------------------------------------
# Historique
# --------------------------------------------------------------------------

@bp.get("/historique")
@require_admin
def history():
    sessions = query(
        """SELECT x.*,
                  COUNT(s.id)       AS students,
                  AVG(s.final_score) AS average,
                  MIN(s.final_score) AS worst,
                  MAX(s.final_score) AS best,
                  SUM(s.exit_count)  AS exits
             FROM session x LEFT JOIN student s ON s.session_id = x.id
            WHERE x.status = 'closed'
            GROUP BY x.id ORDER BY x.closed_at DESC""",
    )
    return render_template("admin_history.html", sessions=sessions)


@bp.post("/sessions/<int:session_id>/delete")
@require_admin
def delete_session(session_id):
    execute("DELETE FROM session WHERE id = ?", (session_id,))
    return redirect(url_for("admin.history"))
