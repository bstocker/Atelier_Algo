"""Parcours etudiant : identification, exercices, surveillance, remise."""

import json
import random
import secrets

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, session, url_for)

from . import exercises as ex
from . import scoring
from .db import execute, now, query

bp = Blueprint("student", __name__)

TOKEN_KEY = "student_token"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def current_student():
    """Etudiant identifie par le cookie de session, ou None."""
    token = session.get(TOKEN_KEY)
    if not token:
        return None
    return query(
        """SELECT s.*, x.status AS session_status, x.title AS session_title,
                  x.code AS session_code
             FROM student s JOIN session x ON x.id = s.session_id
            WHERE s.token = ?""",
        (token,), one=True,
    )


def require_student():
    student = current_student()
    if student is None:
        abort(401, description="Identification requise.")
    return student


def tasks_of(student_id):
    return query(
        "SELECT * FROM task WHERE student_id = ? ORDER BY position",
        (student_id,),
    )


def touch(student_id):
    execute("UPDATE student SET last_seen_at = ? WHERE id = ?",
            (now(), student_id))


def progress_of(student):
    rows = tasks_of(student["id"])
    solved = sum(1 for t in rows if t["solved"])
    shares = scoring.shares_of(rows, ex.answer_space)
    return {
        "solved": solved,
        "total": len(rows),
        "penalty": student["penalty_points"],
        "exits": student["exit_count"],
        # Points laisses sur les exercices reussis a l'arrache : l'eleve doit
        # voir ce que ses essais manques lui ont deja coute.
        "lost": round(scoring.base_score([1.0] * solved, len(rows))
                      - scoring.base_score(shares, len(rows)), 2),
        "score": scoring.final_score(shares, len(rows),
                                     student["penalty_points"]),
    }


def stakes_of(task, total):
    """Ce que l'exercice rapporte encore, et ce que coute un essai manque.

    Descend avec chaque exercice : un bareme qui sanctionne sans prevenir
    serait un piege. L'eleve voit la mise avant de tenter, pas apres.
    """
    choices = ex.answer_space(task["pattern_key"])
    value = scoring.exercise_value(total)
    return {
        "value": round(value, 2),
        "cost": round(scoring.attempt_cost(total, choices), 2),
        "tries": scoring.allowance(choices),
        "wrong": task["wrong_attempts"],
        "worth": round(value * scoring.kept_share(choices,
                                                  task["wrong_attempts"]), 2),
    }


def task_count(student_id):
    return query("SELECT COUNT(*) AS c FROM task WHERE student_id = ?",
                 (student_id,), one=True)["c"]


# --------------------------------------------------------------------------
# Identification
# --------------------------------------------------------------------------

@bp.get("/")
def join_form():
    student = current_student()
    if student and student["session_status"] == "open" \
            and not student["finished_at"]:
        return redirect(url_for("student.exercise_page"))
    return render_template("join.html", error=request.args.get("error"))


@bp.get("/s/<code>")
def join_by_code(code):
    """Lien distribue par l'enseignant : le code est deja dans l'URL."""
    room = query("SELECT * FROM session WHERE code = ?",
                 (code.strip().upper()[:12],), one=True)
    if room is None:
        return redirect(url_for("student.join_form",
                                error="Ce lien ne correspond à aucune session."))
    if room["status"] == "draft":
        return redirect(url_for("student.join_form",
                                error="Cette session n'est pas encore ouverte."))
    if room["status"] == "closed":
        return redirect(url_for("student.join_form",
                                error="Cette session est terminée."))

    student = current_student()
    if student and student["session_id"] == room["id"]:
        if student["finished_at"]:
            return redirect(url_for("student.done_page"))
        return redirect(url_for("student.exercise_page"))

    return render_template("join.html", room=room,
                           error=request.args.get("error"))


@bp.post("/join")
def join():
    first = " ".join(request.form.get("first_name", "").split())[:60]
    last = " ".join(request.form.get("last_name", "").split())[:60]
    code = request.form.get("code", "").strip().upper()[:12]

    if not first or not last:
        return redirect(url_for("student.join_form",
                                error="Nom et prénom sont obligatoires."))

    room = query("SELECT * FROM session WHERE code = ?", (code,), one=True)
    if room is None:
        return redirect(url_for("student.join_form",
                                error="Aucune session avec ce code."))
    if room["status"] == "draft":
        return redirect(url_for("student.join_form",
                                error="Cette session n'est pas encore ouverte."))
    if room["status"] == "closed":
        return redirect(url_for("student.join_form",
                                error="Cette session est terminée."))

    # Un etudiant qui revient (rechargement, coupure reseau) retrouve sa copie.
    existing = query(
        """SELECT * FROM student
            WHERE session_id = ? AND last_name = ? AND first_name = ?""",
        (room["id"], last, first), one=True,
    )
    if existing:
        session[TOKEN_KEY] = existing["token"]
        touch(existing["id"])
        if existing["finished_at"]:
            return redirect(url_for("student.done_page"))
        return redirect(url_for("student.exercise_page"))

    token = secrets.token_urlsafe(24)
    student_id = execute(
        """INSERT INTO student (session_id, first_name, last_name, token,
                                joined_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (room["id"], first, last, token, now(), now()),
    )

    # Chaque etudiant recoit ses propres tailles : la cible differe d'un
    # poste a l'autre, comme le veut la fiche projet.
    rng = random.Random(token)
    keys = json.loads(room["patterns"])
    for position, key in enumerate(keys):
        execute(
            """INSERT INTO task (student_id, pattern_key, position, params)
               VALUES (?, ?, ?, ?)""",
            (student_id, key, position, json.dumps(ex.draw_params(key, rng))),
        )

    session[TOKEN_KEY] = token
    return redirect(url_for("student.exercise_page"))


@bp.post("/logout")
def logout():
    session.pop(TOKEN_KEY, None)
    return redirect(url_for("student.join_form"))


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

@bp.get("/exercice")
def exercise_page():
    student = current_student()
    if student is None:
        return redirect(url_for("student.join_form"))
    if student["finished_at"] or student["session_status"] == "closed":
        return redirect(url_for("student.done_page"))
    return render_template(
        "exercise.html",
        student=student,
        return_delay=scoring.RETURN_DELAY_SECONDS,
    )


@bp.get("/termine")
def done_page():
    student = current_student()
    if student is None:
        return redirect(url_for("student.join_form"))
    rows = tasks_of(student["id"])
    solved = sum(1 for t in rows if t["solved"])
    shares = scoring.shares_of(rows, ex.answer_space)
    score = student["final_score"]
    if score is None:
        score = scoring.final_score(shares, len(rows), student["penalty_points"])
    incidents = query(
        "SELECT * FROM incident WHERE student_id = ? ORDER BY ordinal",
        (student["id"],),
    )
    value = scoring.exercise_value(len(rows))
    # « Q1 » ne dit rien hors de son module. On préfixe donc les intitulés
    # quand la session croise plusieurs sujets, et seulement dans ce cas —
    # même règle que la navigation de l'épreuve.
    keys = [t["pattern_key"] for t in rows]
    situer = len(ex.modules_for(keys)) > 1

    def intitule(key):
        name = ex.PATTERNS[key].name
        return "%s · %s" % (ex.module_of(key).title, name) if situer else name

    return render_template(
        "done.html", student=student, solved=solved, total=len(rows),
        score=score, base=scoring.base_score(shares, len(rows)),
        # Note qu'aurait valu la meme copie sans aucun essai manque : c'est
        # l'ecart, pas le total, qui fait comprendre le bareme.
        clean=scoring.base_score([1.0] * solved, len(rows)),
        value=value, incidents=incidents,
        details=[{
            "name": intitule(t["pattern_key"]),
            "solved": t["solved"],
            "attempts": t["attempts"],
            "wrong": t["wrong_attempts"],
            "points": round(value * scoring.kept_share(
                ex.answer_space(t["pattern_key"]), t["wrong_attempts"]), 2)
                      if t["solved"] else 0.0,
        } for t in rows],
    )


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@bp.get("/api/me")
def api_me():
    student = require_student()
    touch(student["id"])
    rows = tasks_of(student["id"])
    return jsonify({
        "first_name": student["first_name"],
        "last_name": student["last_name"],
        "session_title": student["session_title"],
        "session_status": student["session_status"],
        "finished": bool(student["finished_at"]),
        "progress": progress_of(student),
        # Les intitulés de module ne servent que si la session en croise
        # plusieurs ; sinon ils n'ajouteraient que du bruit.
        "modules": [m.title for m in
                    ex.modules_for([t["pattern_key"] for t in rows])],
        "tasks": [{
            "key": t["pattern_key"],
            "name": ex.PATTERNS[t["pattern_key"]].name,
            "level": ex.PATTERNS[t["pattern_key"]].level,
            "level_name": ex.LEVELS[ex.PATTERNS[t["pattern_key"]].level],
            "module": ex.module_of(t["pattern_key"]).title,
            "solved": bool(t["solved"]),
            "attempts": t["attempts"],
            "wrong": t["wrong_attempts"],
            "stakes": stakes_of(t, len(rows)),
        } for t in rows],
    })


@bp.get("/api/task/<key>")
def api_task(key):
    student = require_student()
    task = query(
        "SELECT * FROM task WHERE student_id = ? AND pattern_key = ?",
        (student["id"], key), one=True,
    )
    if task is None:
        abort(404, description="Exercice absent de cette session.")

    pattern = ex.PATTERNS[key]
    params = json.loads(task["params"])
    stored = json.loads(task["selection"])
    solved = bool(task["solved"])

    payload = {
        "key": key,
        "name": pattern.name,
        "brief": pattern.brief,
        "why": pattern.why,
        "mode": pattern.mode,
        "level": pattern.level,
        "level_name": ex.LEVELS[pattern.level],
        "module": ex.module_of(key).title,
        "params": params,
        "lesson": list(pattern.lesson),
        "solved": solved,
        "attempts": task["attempts"],
        "stakes": stakes_of(task, task_count(student["id"])),
    }

    if pattern.mode == "predict":
        # La cible est la reponse : elle ne descend qu'une fois trouvee.
        payload["code"] = ex.render_code(key, params)
        payload["answer"] = stored.get("answer", "")
        payload["target"] = ex.target_rows(key, params) if solved else None
    elif pattern.mode == "qcm":
        # Ni code ni sortie : une question, quatre propositions. L'ordre des
        # propositions est tire par la copie, il differe d'un eleve a l'autre.
        payload["question"] = pattern.brief
        payload["blanks"] = ex.shuffled_blanks(key, student["token"])
        payload["selection"] = stored
    elif pattern.mode == "debug":
        # Rien a cacher : l'ecart est sous les yeux, c'est l'expliquer
        # qui fait l'exercice.
        payload["code"] = ex.render_code(key, params)
        payload["target"] = ex.target_rows(key, params)
        payload["actual"] = ex.broken_rows(key, params)
        payload["blanks"] = ex.shuffled_blanks(key, student["token"])
        payload["selection"] = stored
    else:
        payload["target"] = ex.target_rows(key, params)
        payload["code"] = ex.render_code(key, params, stored)
        payload["code_template"] = ex.code_template(key, params)
        payload["blanks"] = ex.shuffled_blanks(key, student["token"])
        payload["selection"] = stored

    return jsonify(payload)


@bp.post("/api/task/<key>/check")
def api_check(key):
    student = require_student()
    if student["finished_at"] or student["session_status"] != "open":
        abort(409, description="La session n'accepte plus de réponses.")

    task = query(
        "SELECT * FROM task WHERE student_id = ? AND pattern_key = ?",
        (student["id"], key), one=True,
    )
    if task is None:
        abort(404, description="Exercice absent de cette session.")

    pattern = ex.PATTERNS[key]
    payload = request.get_json(silent=True) or {}
    params = json.loads(task["params"])
    target = ex.target_rows(key, params)
    already = bool(task["solved"])

    if pattern.mode in ("debug", "qcm"):
        # Meme forme dans les deux modes : un menu unique, des phrases, un
        # retour apres coup. Seul l'intitule du menu et la relance changent.
        blank_id = next(iter(pattern.blanks))
        raw = (payload.get("selection") or {}).get(blank_id)
        valid = {o.id for o in pattern.blanks[blank_id][1]}
        chosen = raw if raw in valid else None
        if chosen is None:
            touch(student["id"])
            return jsonify({"complete": False, "ok": False,
                            "message": "Choisissez une cause."
                                       if pattern.mode == "debug"
                                       else "Choisissez une réponse."})
        execute("UPDATE task SET selection = ? WHERE id = ?",
                (json.dumps({blank_id: chosen}), task["id"]))
        ok = chosen == pattern.ref[blank_id]
        note = ex.option_note(key, blank_id, chosen)
        produced, diff, trace, infinite = None, None, None, False
    elif pattern.mode == "predict":
        answer = (payload.get("answer") or "")[:4000]
        execute("UPDATE task SET selection = ? WHERE id = ?",
                (json.dumps({"answer": answer}), task["id"]))
        produced = answer.replace("\r\n", "\n").split("\n")
        while produced and not produced[-1].strip():
            produced.pop()
        if not produced:
            touch(student["id"])
            return jsonify({"complete": False, "ok": False,
                            "message": "Écrivez la sortie attendue."})
        ok, diff = ex.compare(produced, target)
        trace, infinite, note = None, False, None
    else:
        raw = payload.get("selection") or {}
        valid = {b: {o.id for o in opts}
                 for b, (_lbl, opts) in pattern.blanks.items()}
        selection = {b: raw.get(b) for b in pattern.blanks
                     if raw.get(b) in valid[b]}
        execute("UPDATE task SET selection = ? WHERE id = ?",
                (json.dumps(selection), task["id"]))

        if len(selection) < len(pattern.blanks):
            touch(student["id"])
            return jsonify({"complete": False, "ok": False,
                            "code": ex.render_code(key, params, selection),
                            "message": "Complétez tous les menus."})

        # La trace deroule le choix de l'eleve, pas la reponse attendue : une
        # condition fausse produit une trace fausse, et c'est la qu'on la voit.
        trace = ex.build_trace(key, params, selection)
        try:
            produced = ex.build_rows(key, params, selection)
            infinite = False
        except ex.InfiniteLoop:
            produced, infinite = [], True
        ok, diff = (False, []) if infinite else ex.compare(produced, target)
        note = None

    execute("UPDATE task SET attempts = attempts + 1 WHERE id = ?", (task["id"],))
    if ok and not already:
        execute("UPDATE task SET solved = 1, solved_at = ? WHERE id = ?",
                (now(), task["id"]))
    elif not ok and not already:
        # Seuls les essais manques d'un exercice pas encore trouve coutent :
        # revenir sur un exercice deja valide ne peut plus rien lui retirer.
        execute("UPDATE task SET wrong_attempts = wrong_attempts + 1 "
                "WHERE id = ?", (task["id"],))
    touch(student["id"])
    student = current_student()  # relit les compteurs a jour
    task = query("SELECT * FROM task WHERE id = ?", (task["id"],), one=True)

    body = {
        "complete": True,
        "ok": ok,
        "rows": produced,
        "trace": trace,
        "infinite": infinite,
        "first_time": ok and not already,
        "stakes": stakes_of(task, task_count(student["id"])),
        "progress": progress_of(student),
    }

    if pattern.mode in ("debug", "qcm"):
        body["note"] = note
        return jsonify(body)

    if pattern.mode == "predict":
        if ok:
            body["diff"] = diff
            body["target"] = target      # revelee seulement une fois trouvee
        else:
            # Ne rien reveler : verdict ligne a ligne sur ce que l'eleve a
            # ecrit, sans le contenu attendu ni le nombre de lignes cibles.
            body["diff"] = [{"line": d["line"], "ok": d["ok"], "got": d["got"]}
                            for d in diff if d["got"] is not None]
            body["count_mismatch"] = len(produced) != len(target)
    else:
        body["diff"] = diff
        body["code"] = ex.render_code(key, params, selection)

    return jsonify(body)


@bp.post("/api/incident")
def api_incident():
    """Enregistre une sortie de fenetre et renvoie la sanction associee."""
    student = require_student()
    if student["finished_at"] or student["session_status"] != "open":
        return jsonify({"ignored": True}), 200

    payload = request.get_json(silent=True) or {}
    kind = payload.get("kind")
    if kind not in ("blur", "hidden", "fullscreen"):
        kind = "blur"

    ordinal = student["exit_count"] + 1
    penalty = scoring.penalty_for(ordinal)
    incident_id = execute(
        """INSERT INTO incident (student_id, ordinal, kind, penalty, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (student["id"], ordinal, kind, penalty, now()),
    )
    execute(
        """UPDATE student
              SET exit_count = ?, penalty_points = penalty_points + ?,
                  last_seen_at = ?
            WHERE id = ?""",
        (ordinal, penalty, now(), student["id"]),
    )

    student = current_student()
    return jsonify({
        "incident_id": incident_id,
        "ordinal": ordinal,
        "penalty": penalty,
        "total_penalty": student["penalty_points"],
        "delay": scoring.RETURN_DELAY_SECONDS,
        "progress": progress_of(student),
    })


@bp.post("/api/incident/<int:incident_id>/return")
def api_incident_return(incident_id):
    """Note le delai de retour, pour que l'enseignant le voie."""
    student = require_student()
    payload = request.get_json(silent=True) or {}
    try:
        ms = max(0, min(600000, int(payload.get("ms", 0))))
    except (TypeError, ValueError):
        ms = 0
    execute(
        """UPDATE incident SET returned_ms = ?
            WHERE id = ? AND student_id = ? AND returned_ms IS NULL""",
        (ms, incident_id, student["id"]),
    )
    touch(student["id"])
    return jsonify({"ok": True})


@bp.post("/api/heartbeat")
def api_heartbeat():
    student = require_student()
    touch(student["id"])
    return jsonify(progress_of(student))


@bp.post("/api/finish")
def api_finish():
    student = require_student()
    if not student["finished_at"]:
        rows = tasks_of(student["id"])
        score = scoring.final_score(scoring.shares_of(rows, ex.answer_space),
                                    len(rows), student["penalty_points"])
        execute(
            "UPDATE student SET finished_at = ?, final_score = ? WHERE id = ?",
            (now(), score, student["id"]),
        )
    return jsonify({"ok": True, "redirect": url_for("student.done_page")})
