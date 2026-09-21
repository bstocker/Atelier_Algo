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
from . import qcm
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
    # Module puis niveau : l'enseignant choisit d'abord un sujet, ensuite
    # une difficulte, plutot que de lire dix-huit intitules d'affilee.
    return render_template(
        "admin_dashboard.html", sessions=sessions,
        catalogue=ex.catalogue(), levels=ex.LEVELS,
        imported=[{"key": row["key"], "title": row["title"],
                   "questions": len(questions), "source": row["source"],
                   "imported_at": row["imported_at"]}
                  for row, questions in qcm.imported()],
        notice=request.args.get("ok", ""),
        error=request.args.get("error", ""),
    )


# --------------------------------------------------------------------------
# Chapitre QCM : import, retrait, modele
# --------------------------------------------------------------------------

@bp.post("/qcm")
@require_admin
def import_qcm():
    """Depose un classeur Excel : un sous-module de plus au chapitre QCM."""
    upload = request.files.get("workbook")
    if upload is None or not upload.filename:
        return redirect(url_for("admin.dashboard",
                                error="Choisissez un fichier .xlsx."))
    title = request.form.get("title", "") or upload.filename.rsplit(".", 1)[0]
    try:
        questions = qcm.parse(upload.stream)
        key = qcm.save(title, request.form.get("summary", ""), questions,
                       source=upload.filename)
    except qcm.BadWorkbook as refus:
        return redirect(url_for("admin.dashboard", error=str(refus)))

    # Le catalogue doit porter le nouveau module des cette redirection.
    qcm.sync(force=True)
    module = ex.MODULE_BY_KEY[key]
    return redirect(url_for(
        "admin.dashboard",
        ok="« %s » importé : %d question%s." % (module.title, len(questions),
                                                "s" if len(questions) > 1 else "")))


@bp.post("/qcm/<key>/delete")
@require_admin
def delete_qcm(key):
    """Retire un module importe, sauf s'il sert deja dans une session."""
    sessions = qcm.used_by(key)
    if sessions:
        return redirect(url_for(
            "admin.dashboard",
            error="Ce QCM est utilisé par %d session%s (%s) : il ne peut pas "
                  "être supprimé sans vider ces copies."
                  % (len(sessions), "s" if len(sessions) > 1 else "",
                     ", ".join(sessions[:3]))))
    if not qcm.delete(key):
        return redirect(url_for("admin.dashboard", error="QCM introuvable."))
    qcm.sync(force=True)
    return redirect(url_for("admin.dashboard", ok="QCM supprimé."))


@bp.get("/qcm/modele.xlsx")
@require_admin
def qcm_model():
    """Le classeur modele, rempli avec le QCM Docker livre avec l'appli."""
    from .modules import qcm_docker
    try:
        book = qcm.model_workbook(qcm_docker.PATTERNS)
    except qcm.BadWorkbook as refus:
        return redirect(url_for("admin.dashboard", error=str(refus)))
    return Response(
        book,
        mimetype="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet",
        headers={"Content-Disposition":
                 'attachment; filename="modele-qcm.xlsx"'},
    )


@bp.get("/api/patterns/<key>")
@require_admin
def api_pattern(key):
    """Les attendus d'un exercice, pour la fiche de l'enseignant.

    Le tirage est fait sur une graine fixe : deux lectures de la meme
    fiche montrent le meme enonce, alors que chaque eleve, lui, recevra
    le sien. Rien n'est cache ici — la reponse de reference et la note
    d'enseignant en font partie, la route est derriere l'authentification.
    """
    if key not in ex.PATTERNS:
        abort(404, description="Exercice inconnu.")
    pattern = ex.PATTERNS[key]
    params = ex.draw_params(key, random.Random(key))
    return jsonify({
        "key": key,
        "name": pattern.name,
        "brief": pattern.brief,
        "why": pattern.why,
        "mode": pattern.mode,
        "level": pattern.level,
        "level_name": ex.LEVELS[pattern.level],
        "module": ex.module_of(key).title,
        "chapter": ex.chapter_of(key).title,
        "lesson": list(pattern.lesson),
        "teacher_note": pattern.teacher_note,
        "code": ex.render_code(key, params, dict(pattern.ref)),
        "target": ex.target_rows(key, params),
        "actual": ex.broken_rows(key, params),
        "blanks": [
            {"id": blank_id,
             "label": label,
             "options": [{"c": o.c,
                          "note": o.note,
                          "ok": o.id == pattern.ref.get(blank_id)}
                         for o in options]}
            for blank_id, (label, options) in pattern.blanks.items()
        ],
    })


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
        tasks = query("SELECT * FROM task WHERE student_id = ?",
                      (student["id"],))
        shares = scoring.shares_of(tasks, ex.answer_space)
        score = scoring.final_score(shares, total, student["penalty_points"])
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
        motifs=[ex.PATTERNS[k] for k in keys],
        modules=ex.modules_for(keys),
        levels=ex.LEVELS,
        # Lien a transmettre : le code y est deja, l'etudiant ne saisit
        # que son nom et son prenom.
        join_url=url_for("student.join_by_code", code=room["code"],
                         _external=True),
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
        ordered = [tasks[k] for k in keys if k in tasks]
        solved = sum(1 for t in tasks.values() if t["solved"])
        shares = scoring.shares_of(ordered, ex.answer_space)
        live = scoring.final_score(shares, total, student["penalty_points"])
        rows.append({
            "id": student["id"],
            "name": "%s %s" % (student["last_name"].upper(),
                               student["first_name"]),
            "solved": solved,
            "total": total,
            "attempts": sum(t["attempts"] for t in tasks.values()),
            "wrong": sum(t["wrong_attempts"] for t in tasks.values()),
            # Ce que les essais manques ont deja coute a la copie.
            "lost": round(scoring.base_score([1.0] * solved, total)
                          - scoring.base_score(shares, total), 2),
            "exits": student["exit_count"],
            "penalty": student["penalty_points"],
            "score": student["final_score"] if student["final_score"] is not None
                     else live,
            "finished": bool(student["finished_at"]),
            "last_seen": student["last_seen_at"],
            "cells": [
                {"key": k,
                 "solved": bool(tasks[k]["solved"]) if k in tasks else False,
                 "attempts": tasks[k]["attempts"] if k in tasks else 0,
                 "wrong": tasks[k]["wrong_attempts"] if k in tasks else 0}
                for k in keys
            ],
        })

    scores = [r["score"] for r in rows]
    return {
        "status": room["status"],
        "code": room["code"],
        "title": room["title"],
        # L'intitulé complet part en infobulle : deux QCM ont tous les deux
        # une « Q1 », et la colonne est trop étroite pour l'énoncé.
        "patterns": [{"key": k, "name": ex.PATTERNS[k].name,
                      "brief": ex.PATTERNS[k].brief,
                      "module": ex.module_of(k).title} for k in keys],
        "students": rows,
        "stats": {
            "count": len(rows),
            "finished": sum(1 for r in rows if r["finished"]),
            "average": round(sum(scores) / len(scores), 2) if scores else None,
            "exits": sum(r["exits"] for r in rows),
            "wrong": sum(r["wrong"] for r in rows),
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
                     "Essais manques", "Points perdus", "Sorties", "Penalite",
                     "Note sur 20", "Termine"])
    for row in data["students"]:
        writer.writerow([row["name"], row["solved"], row["total"],
                         row["attempts"], row["wrong"],
                         ("%.2f" % row["lost"]).replace(".", ","),
                         row["exits"], row["penalty"],
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
