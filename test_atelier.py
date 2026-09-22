"""Tests de bout en bout : session, exercices, penalites, notation."""

import io
import itertools
import json
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
import urllib.parse

from markupsafe import escape

from atelier import (create_app, db, load_env_file, exercises as ex, qcm,
                     scoring, student)


def tirages(pattern):
    """Tous les paramètres possibles d'un exercice, tirages croisés.

    Les exercices n'ont pas tous une seule dimension : certains en tirent
    plusieurs, d'autres en dérivent (une phrase, les valeurs d'un tableau).
    """
    specs = ex.specs(pattern)
    noms = [nom for nom, _lo, _hi in specs]
    for combinaison in itertools.product(*[range(lo, hi + 1)
                                           for _n, lo, hi in specs]):
        params = dict(zip(noms, combinaison))
        if pattern.derive:
            params.update(pattern.derive(params))
        yield params


def un_exercice(mode):
    """Premier exercice du catalogue dans ce mode.

    Les tests du mode examen doivent couvrir les quatre modes ; les nommer
    en dur les casserait au premier remaniement du catalogue.
    """
    for key in ex.ALL_KEYS:
        if ex.PATTERNS[key].mode == mode:
            return key
    raise AssertionError("aucun exercice en mode %s" % mode)


class AtelierTest(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({
            "TESTING": True,
            "DATABASE": self.path,
            "SECRET_KEY": "test",
            "ADMIN_USER": "prof",
            "ADMIN_PASSWORD": "secret",
        })
        self.admin = self.app.test_client()
        self.admin.post("/admin/login",
                        data={"username": "prof", "password": "secret"})

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    # -- utilitaires -------------------------------------------------------

    def make_session(self, patterns=("carre", "triangle_rect"), launch=True):
        resp = self.admin.post("/admin/sessions", data={
            "title": "TP test", "patterns": list(patterns)})
        session_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        if launch:
            self.admin.post("/admin/sessions/%d/open" % session_id)
        page = self.admin.get("/admin/sessions/%d" % session_id)
        html = page.get_data(as_text=True)
        code = html.split('class="joincode mono">')[1].split("<")[0].strip()
        return session_id, code

    def join(self, code, first="Ada", last="Lovelace"):
        client = self.app.test_client()
        resp = client.post("/join", data={
            "first_name": first, "last_name": last, "code": code})
        return client, resp

    def solve(self, client, key):
        """Soumet la bonne reponse, quel que soit le mode de l'exercice."""
        task = client.get("/api/task/" + key).get_json()
        pattern = ex.PATTERNS[key]
        if pattern.mode == "predict":
            attendu = ex.target_rows(key, task["params"])
            body = {"answer": "\n".join(attendu)}
        else:
            body = {"selection": dict(pattern.ref)}
        return client.post("/api/task/%s/check" % key, json=body).get_json()

    # -- tests -------------------------------------------------------------

    def test_session_must_be_launched_by_admin(self):
        session_id, code = self.make_session(launch=False)
        _, resp = self.join(code)
        self.assertIn("error=", resp.headers["Location"])

        self.admin.post("/admin/sessions/%d/open" % session_id)
        _, resp = self.join(code)
        self.assertTrue(resp.headers["Location"].endswith("/exercice"))

    def test_the_composition_form_starts_with_nothing_checked(self):
        """L'enseignant coche son epreuve : rien n'est retenu d'avance."""
        page = self.admin.get("/admin/").get_data(as_text=True)
        cases = page.count('name="patterns"')
        self.assertGreater(cases, 0)
        # Aucune case cochee, ni parmi les exercices ni ailleurs.
        self.assertNotIn("checked", page)

    def test_a_session_without_any_exercise_is_refused(self):
        """Un formulaire tout decoche ne doit pas donner le catalogue entier."""
        resp = self.admin.post("/admin/sessions", data={"title": "Vide"})
        self.assertIn("error=", resp.headers["Location"])
        self.assertEqual(
            self.admin.get("/admin/api/sessions/1/live").status_code, 404)

    def test_admin_area_requires_login(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/admin/").status_code, 302)
        self.assertEqual(anon.get("/admin/historique").status_code, 302)
        session_id, _ = self.make_session()
        self.assertEqual(
            anon.get("/admin/api/sessions/%d/live" % session_id).status_code, 401)

    def test_identification_required_for_api(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/me").status_code, 401)

    def test_join_requires_name(self):
        _, code = self.make_session()
        client = self.app.test_client()
        resp = client.post("/join", data={"first_name": "", "last_name": "X",
                                          "code": code})
        self.assertIn("obligatoires", resp.headers["Location"])

    def test_reference_selection_is_accepted_for_every_pattern(self):
        _, code = self.make_session(patterns=ex.ALL_KEYS)
        client, _ = self.join(code)
        for key in ex.ALL_KEYS:
            with self.subTest(pattern=key):
                res = self.solve(client, key)
                self.assertTrue(res["ok"], key)
                self.assertTrue(res["first_time"])

    def test_wrong_selection_is_rejected_and_diffed(self):
        _, code = self.make_session(patterns=("triangle_rect",))
        client, _ = self.join(code)
        res = client.post("/api/task/triangle_rect/check",
                          json={"selection": {"stars": "c"}}).get_json()
        self.assertFalse(res["ok"])
        self.assertTrue(any(not d["ok"] for d in res["diff"]))

    def test_incomplete_selection_is_not_an_attempt(self):
        _, code = self.make_session(patterns=("triangle_droite",))
        client, _ = self.join(code)
        res = client.post("/api/task/triangle_droite/check",
                          json={"selection": {"spaces": "a"}}).get_json()
        self.assertFalse(res["complete"])
        self.assertEqual(client.get("/api/task/triangle_droite")
                         .get_json()["attempts"], 0)

    def test_api_never_leaks_the_expected_selection(self):
        _, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        payload = client.get("/api/task/carre").get_json()
        self.assertNotIn("ref", payload)
        self.assertNotIn("correct", json.dumps(payload))

    def test_exit_penalties_escalate(self):
        _, code = self.make_session()
        client, _ = self.join(code)
        expected = [(1, 0.0, 0.0), (2, 2.0, 2.0), (3, 3.0, 5.0), (4, 3.0, 8.0)]
        for ordinal, penalty, total in expected:
            res = client.post("/api/incident", json={"kind": "blur"}).get_json()
            self.assertEqual(res["ordinal"], ordinal)
            self.assertEqual(res["penalty"], penalty)
            self.assertEqual(res["total_penalty"], total)

    def test_return_delay_is_recorded_once(self):
        _, code = self.make_session()
        client, _ = self.join(code)
        incident = client.post("/api/incident", json={"kind": "hidden"}).get_json()
        url = "/api/incident/%d/return" % incident["incident_id"]
        self.assertEqual(client.post(url, json={"ms": 1400}).status_code, 200)
        client.post(url, json={"ms": 99000})
        page = client.get("/termine").get_data(as_text=True)
        self.assertIn("1.4 s", page)

    def test_score_is_out_of_20_minus_penalties(self):
        _, code = self.make_session(patterns=("carre", "triangle_rect",
                                              "triangle_inv", "losange"))
        client, _ = self.join(code)
        self.solve(client, "carre")
        self.solve(client, "triangle_rect")          # 2/4 -> 10 points
        client.post("/api/incident", json={"kind": "blur"})   # avertissement
        client.post("/api/incident", json={"kind": "blur"})   # -2
        progress = client.post("/api/heartbeat").get_json()
        self.assertEqual(progress["score"], 8.0)

    def test_a_failed_attempt_costs_points_on_that_exercise(self):
        """Un motif trouvé après un essai manqué rapporte moins qu'un sans faute."""
        _, code = self.make_session(patterns=("carre", "triangle_rect"))
        client, _ = self.join(code)

        client.post("/api/task/carre/check", json={"selection": {"stars": "c"}})
        task = client.get("/api/task/carre").get_json()
        self.assertEqual(task["stakes"]["wrong"], 1)
        # Quatre réponses, donc trois fausses : un tiers de 10 points.
        self.assertEqual(task["stakes"]["value"], 10.0)
        self.assertEqual(task["stakes"]["cost"], 3.33)
        self.assertEqual(task["stakes"]["worth"], 6.67)

        res = self.solve(client, "carre")
        self.assertTrue(res["ok"])
        self.assertEqual(res["progress"]["score"], 6.67)
        self.assertEqual(res["progress"]["lost"], 3.33)

    def test_trying_every_answer_earns_nothing(self):
        """L'élève qui essaie les réponses une par une finit à zéro."""
        _, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        bonne = ex.PATTERNS["carre"].ref["stars"]
        fausses = [o.id for o in ex.PATTERNS["carre"].blanks["stars"][1]
                   if o.id != bonne]
        for option in fausses:
            client.post("/api/task/carre/check",
                        json={"selection": {"stars": option}})
        res = self.solve(client, "carre")
        self.assertTrue(res["ok"])
        self.assertEqual(res["stakes"]["worth"], 0.0)
        self.assertEqual(res["progress"]["solved"], 1)
        self.assertEqual(res["progress"]["score"], 0.0)

    def test_an_exercise_already_solved_costs_nothing_more(self):
        """Revenir sur un motif validé ne peut plus lui retirer de points."""
        _, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        self.solve(client, "carre")
        res = client.post("/api/task/carre/check",
                          json={"selection": {"stars": "c"}}).get_json()
        self.assertFalse(res["ok"])
        self.assertEqual(res["stakes"]["wrong"], 0)
        self.assertEqual(res["progress"]["score"], 20.0)

    def test_an_incomplete_answer_costs_nothing(self):
        """Un menu laissé vide n'est pas un essai : rien n'est retiré."""
        _, code = self.make_session(patterns=("triangle_droite",))
        client, _ = self.join(code)
        client.post("/api/task/triangle_droite/check",
                    json={"selection": {"spaces": "a"}})
        self.assertEqual(client.get("/api/task/triangle_droite")
                         .get_json()["stakes"]["wrong"], 0)

    def test_the_cost_of_an_attempt_follows_the_answer_space(self):
        """Deux menus de quatre options : seize réponses, un essai coûte moins."""
        _, code = self.make_session(patterns=("carre", "triangle_droite"))
        client, _ = self.join(code)
        un_menu = client.get("/api/task/carre").get_json()["stakes"]
        deux_menus = client.get("/api/task/triangle_droite").get_json()["stakes"]
        self.assertEqual(un_menu["value"], deux_menus["value"])
        self.assertEqual(un_menu["tries"], 3)
        self.assertEqual(deux_menus["tries"], 15)
        self.assertGreater(un_menu["cost"], deux_menus["cost"])

    def test_the_student_sees_the_stakes_before_answering(self):
        """La mise est annoncée avant le geste, jamais découverte après."""
        _, code = self.make_session(patterns=("carre", "triangle_rect"))
        client, _ = self.join(code)
        stakes = client.get("/api/task/carre").get_json()["stakes"]
        self.assertEqual(stakes["wrong"], 0)
        self.assertEqual(stakes["worth"], stakes["value"])
        page = client.get("/exercice").get_data(as_text=True)
        self.assertIn("essai manqué", page)

    def test_failed_attempts_reach_the_teacher(self):
        session_id, code = self.make_session(patterns=("carre", "triangle_rect"))
        client, _ = self.join(code)
        client.post("/api/task/carre/check", json={"selection": {"stars": "c"}})
        self.solve(client, "carre")

        live = self.admin.get("/admin/api/sessions/%d/live" % session_id) \
                         .get_json()
        row = live["students"][0]
        self.assertEqual(row["wrong"], 1)
        self.assertEqual(row["lost"], 3.33)
        self.assertEqual(row["score"], 6.67)
        self.assertEqual(live["stats"]["wrong"], 1)
        self.assertEqual([c["wrong"] for c in row["cells"]], [1, 0])

        csv_text = self.admin.get("/admin/sessions/%d/export.csv" % session_id) \
                             .get_data(as_text=True)
        self.assertIn("Essais manques", csv_text)
        self.assertIn("6,67", csv_text)

    def test_closing_a_session_freezes_the_reduced_score(self):
        session_id, code = self.make_session(patterns=("carre", "triangle_rect"))
        client, _ = self.join(code)
        client.post("/api/task/carre/check", json={"selection": {"stars": "c"}})
        self.solve(client, "carre")
        self.solve(client, "triangle_rect")
        self.admin.post("/admin/sessions/%d/close" % session_id)
        live = self.admin.get("/admin/api/sessions/%d/live" % session_id) \
                         .get_json()
        self.assertEqual(live["students"][0]["score"], 16.67)

    def test_the_report_details_what_each_exercise_earned(self):
        _, code = self.make_session(patterns=("carre", "triangle_rect"))
        client, _ = self.join(code)
        client.post("/api/task/carre/check", json={"selection": {"stars": "c"}})
        self.solve(client, "carre")
        client.post("/api/finish")
        page = client.get("/termine").get_data(as_text=True)
        self.assertIn("Essais manqués", page)
        self.assertIn("6.67", page)      # points gardés sur le motif arraché

    def test_score_never_goes_below_zero(self):
        _, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        for _ in range(6):
            client.post("/api/incident", json={"kind": "blur"})
        self.assertEqual(client.post("/api/heartbeat").get_json()["score"], 0.0)

    def test_closing_session_freezes_scores_and_blocks_answers(self):
        session_id, code = self.make_session(patterns=("carre", "triangle_rect"))
        client, _ = self.join(code)
        self.solve(client, "carre")

        self.admin.post("/admin/sessions/%d/close" % session_id)

        blocked = client.post("/api/task/triangle_rect/check",
                              json={"selection": dict(ex.PATTERNS["triangle_rect"].ref)})
        self.assertEqual(blocked.status_code, 409)

        live = self.admin.get("/admin/api/sessions/%d/live" % session_id).get_json()
        self.assertEqual(live["status"], "closed")
        self.assertEqual(live["students"][0]["score"], 10.0)
        self.assertTrue(live["students"][0]["finished"])

    def test_closed_session_appears_in_history(self):
        session_id, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        self.solve(client, "carre")
        self.admin.post("/admin/sessions/%d/close" % session_id)
        page = self.admin.get("/admin/historique").get_data(as_text=True)
        self.assertIn("TP test", page)
        self.assertIn("20.00", page)

    def test_history_survives_and_csv_exports(self):
        session_id, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code, first="Alan", last="Turing")
        self.solve(client, "carre")
        self.admin.post("/admin/sessions/%d/close" % session_id)
        csv_body = self.admin.get("/admin/sessions/%d/export.csv" % session_id)
        text = csv_body.get_data(as_text=True)
        self.assertIn("TURING Alan", text)
        self.assertIn("20,00", text)

    def test_rejoining_recovers_the_same_copy(self):
        _, code = self.make_session(patterns=("carre", "triangle_rect"))
        client, _ = self.join(code)
        self.solve(client, "carre")
        again, resp = self.join(code)          # nouveau navigateur, meme identite
        me = again.get("/api/me").get_json()
        self.assertEqual(me["progress"]["solved"], 1)

    def test_each_student_gets_its_own_size(self):
        _, code = self.make_session(patterns=("carre",))
        sizes = set()
        for i in range(12):
            client, _ = self.join(code, first="Eleve%d" % i, last="Test")
            sizes.add(client.get("/api/task/carre").get_json()["params"]["n"])
        self.assertGreater(len(sizes), 1)

    def test_students_are_isolated_from_each_other(self):
        _, code = self.make_session(patterns=("carre",))
        a, _ = self.join(code, first="Ada", last="Lovelace")
        b, _ = self.join(code, first="Alan", last="Turing")
        self.solve(client=a, key="carre")
        self.assertEqual(b.post("/api/heartbeat").get_json()["solved"], 0)

    def test_deleting_a_session_removes_its_copies(self):
        session_id, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        self.solve(client, "carre")
        client.post("/api/incident", json={"kind": "blur"})
        self.admin.post("/admin/sessions/%d/close" % session_id)
        self.admin.post("/admin/sessions/%d/delete" % session_id)

        page = self.admin.get("/admin/historique").get_data(as_text=True)
        self.assertNotIn("TP test", page)
        with self.app.app_context():
            from atelier.db import query as q
            self.assertEqual(q("SELECT COUNT(*) c FROM student", one=True)["c"], 0)
            self.assertEqual(q("SELECT COUNT(*) c FROM task", one=True)["c"], 0)
            self.assertEqual(q("SELECT COUNT(*) c FROM incident", one=True)["c"], 0)

    def test_live_view_reports_every_student(self):
        session_id, code = self.make_session(patterns=("carre", "triangle_rect"))
        for i in range(5):
            client, _ = self.join(code, first="Eleve%d" % i, last="Test")
            if i < 3:
                self.solve(client, "carre")
        live = self.admin.get("/admin/api/sessions/%d/live" % session_id).get_json()
        self.assertEqual(len(live["students"]), 5)
        self.assertEqual(sum(s["solved"] for s in live["students"]), 3)
        self.assertEqual(live["stats"]["average"], 6.0)   # 3 x 10 / 5

    def test_intro_exercise_comes_first_and_carries_a_lesson(self):
        self.assertEqual(ex.ALL_KEYS[0], "ligne")
        _, code = self.make_session(patterns=("ligne",))
        client, _ = self.join(code)
        task = client.get("/api/task/ligne").get_json()
        self.assertTrue(task["lesson"])
        self.assertEqual(len(task["target"]), 1)   # une seule ligne

    def test_trace_follows_the_student_choice_not_the_answer(self):
        _, code = self.make_session(patterns=("ligne",))
        client, _ = self.join(code)
        n = client.get("/api/task/ligne").get_json()["params"]["n"]

        # `j <= n` : un tour de trop, l'erreur de borne classique.
        res = client.post("/api/task/ligne/check",
                          json={"selection": {"etoiles": "b"}}).get_json()
        self.assertFalse(res["ok"])
        steps = res["trace"]
        self.assertEqual(len(steps), n + 2)          # n+1 tours, puis la sortie
        self.assertTrue(all(s["vrai"] for s in steps[:-1]))
        self.assertFalse(steps[-1]["vrai"])
        self.assertEqual(steps[-2]["sortie"], "*" * (n + 1))
        # Le test est affiche avec ses valeurs, pas sous forme abstraite.
        self.assertEqual(steps[0]["test"], "0 <= %d" % n)

        res = client.post("/api/task/ligne/check",
                          json={"selection": {"etoiles": "a"}}).get_json()
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["trace"]), n + 1)
        self.assertEqual(res["trace"][-1]["test"], "%d < %d" % (n, n))

    def test_patterns_without_a_trace_return_none(self):
        _, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        res = client.post("/api/task/carre/check",
                          json={"selection": {"stars": "a"}}).get_json()
        self.assertIsNone(res["trace"])

    def test_predict_never_sends_the_expected_output(self):
        _, code = self.make_session(patterns=("predire_triangle",))
        client, _ = self.join(code)
        task = client.get("/api/task/predire_triangle").get_json()
        self.assertEqual(task["mode"], "predict")
        self.assertIsNone(task["target"])
        self.assertNotIn("blanks", task)

        attendu = ex.target_rows("predire_triangle", task["params"])
        res = client.post("/api/task/predire_triangle/check",
                          json={"answer": "n'importe quoi"}).get_json()
        self.assertFalse(res["ok"])
        self.assertNotIn("target", res)
        # Aucune ligne attendue ne doit transiter, ni le nombre de lignes.
        self.assertTrue(all("want" not in d for d in res["diff"]))
        self.assertEqual(len(res["diff"]), 1)
        self.assertTrue(res["count_mismatch"])
        self.assertNotIn("\n".join(attendu), json.dumps(res))

    def test_predict_reveals_the_output_once_found(self):
        _, code = self.make_session(patterns=("predire_magique",))
        client, _ = self.join(code)
        res = self.solve(client, "predire_magique")
        self.assertTrue(res["ok"])
        self.assertEqual(res["target"], res["rows"])

    def test_predict_ignores_trailing_blank_lines(self):
        _, code = self.make_session(patterns=("predire_triangle",))
        client, _ = self.join(code)
        params = client.get("/api/task/predire_triangle").get_json()["params"]
        attendu = ex.target_rows("predire_triangle", params)
        res = client.post("/api/task/predire_triangle/check",
                          json={"answer": "\r\n".join(attendu) + "\r\n\n  \n"}).get_json()
        self.assertTrue(res["ok"])

    def test_empty_prediction_is_not_an_attempt(self):
        _, code = self.make_session(patterns=("predire_triangle",))
        client, _ = self.join(code)
        res = client.post("/api/task/predire_triangle/check",
                          json={"answer": "   \n\n"}).get_json()
        self.assertFalse(res["complete"])
        self.assertEqual(client.get("/api/task/predire_triangle")
                         .get_json()["attempts"], 0)

    def test_infinite_loop_is_reported_not_crashed(self):
        _, code = self.make_session(patterns=("tantque",))
        client, _ = self.join(code)
        res = client.post("/api/task/tantque/check",
                          json={"selection": {"incr": "d"}}).get_json()
        self.assertTrue(res["complete"])
        self.assertTrue(res["infinite"])
        self.assertFalse(res["ok"])
        self.assertTrue(res["trace"][-1]["infinite"])
        self.assertTrue(res["trace"][-1]["vrai"])   # le test reste vrai

    def test_joining_by_url_needs_no_code(self):
        session_id, code = self.make_session(patterns=("ligne",))
        page = self.app.test_client().get("/s/" + code)
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('name="code" value="%s"' % code, html)
        self.assertNotIn("code-input", html)   # pas de champ a saisir

        client = self.app.test_client()
        resp = client.post("/join", data={
            "first_name": "Ada", "last_name": "Lovelace", "code": code})
        self.assertTrue(resp.headers["Location"].endswith("/exercice"))

    def test_join_url_rejects_unknown_or_closed_sessions(self):
        session_id, code = self.make_session(patterns=("ligne",))
        resp = self.app.test_client().get("/s/ZZZZZZ")
        self.assertIn("error=", resp.headers["Location"])

        self.admin.post("/admin/sessions/%d/close" % session_id)
        resp = self.app.test_client().get("/s/" + code)
        self.assertIn("error=", resp.headers["Location"])

    def test_admin_page_shows_the_shareable_link(self):
        session_id, code = self.make_session(patterns=("ligne",))
        html = self.admin.get("/admin/sessions/%d" % session_id) \
                         .get_data(as_text=True)
        self.assertIn("/s/" + code, html)

    def test_dashboard_groups_exercises_by_module_then_level(self):
        html = self.admin.get("/admin/").get_data(as_text=True)
        for module in ex.MODULES:
            self.assertIn(module.title, html)
            self.assertIn('data-module="%s"' % module.key, html)
        for label in ex.LEVELS.values():
            self.assertIn(label, html)
        self.assertIn('data-level="1"', html)

    def test_the_catalogue_folds_by_chapter_and_module(self):
        """Le catalogue se parcourt plié : chapitre ouvert, modules repliés."""
        html = self.admin.get("/admin/").get_data(as_text=True)
        for chapter in ex.CHAPTERS:
            self.assertIn('<details class="chapter" data-chapter="%s" open>'
                          % chapter.key, html)
        for module in ex.MODULES:
            self.assertIn('<details class="module" data-module="%s">'
                          % module.key, html)

    def test_every_exercise_title_opens_its_sheet(self):
        html = self.admin.get("/admin/").get_data(as_text=True)
        self.assertIn('id="exo-sheet"', html)
        for key in ex.ALL_KEYS:
            with self.subTest(exercice=key):
                self.assertIn('data-detail="%s"' % key, html)

    def test_the_session_page_links_its_exercises_to_their_sheet(self):
        session_id, _ = self.make_session(patterns=("ligne", "bug_borne"))
        html = self.admin.get("/admin/sessions/%d" % session_id) \
                         .get_data(as_text=True)
        self.assertIn('id="exo-sheet"', html)
        for key in ("ligne", "bug_borne"):
            self.assertIn('data-detail="%s"' % key, html)

    def test_the_sheet_states_what_is_expected(self):
        """La fiche porte l'énoncé, la sortie attendue et la référence."""
        for key in ex.ALL_KEYS:
            with self.subTest(exercice=key):
                data = self.admin.get("/admin/api/patterns/" + key).get_json()
                pattern = ex.PATTERNS[key]
                self.assertEqual(data["name"], pattern.name)
                self.assertEqual(data["module"], ex.module_of(key).title)
                self.assertEqual(data["chapter"], ex.chapter_of(key).title)
                if pattern.mode == "qcm":
                    # Ni code ni sortie : une question et ses propositions.
                    self.assertEqual(data["target"], [])
                    self.assertEqual(data["code"], "")
                    self.assertTrue(data["brief"])
                else:
                    self.assertTrue(data["target"])
                    # Le code descend complet : aucun @trou@ ne subsiste.
                    self.assertNotIn("@", data["code"])
                for blank in data["blanks"]:
                    bonnes = [o for o in blank["options"] if o["ok"]]
                    self.assertEqual(len(bonnes), 1, blank["id"])

    def test_the_sheet_of_a_debug_exercise_shows_both_outputs(self):
        data = self.admin.get("/admin/api/patterns/bug_borne").get_json()
        self.assertNotEqual(data["target"], data["actual"])
        self.assertTrue(data["teacher_note"].startswith("Défaut"))

    def test_the_sheet_draws_the_same_example_twice(self):
        """Relire une fiche doit montrer le même énoncé, pas un autre tirage."""
        for key in ("ligne", "str_longueur"):
            with self.subTest(exercice=key):
                first = self.admin.get("/admin/api/patterns/" + key).get_json()
                again = self.admin.get("/admin/api/patterns/" + key).get_json()
                self.assertEqual(first, again)

    def test_the_sheet_is_reserved_to_the_teacher(self):
        self.assertEqual(
            self.app.test_client().get("/admin/api/patterns/ligne").status_code,
            401)
        self.assertEqual(
            self.admin.get("/admin/api/patterns/inconnu").status_code, 404)

    def test_student_sees_the_module_of_each_exercise(self):
        _, code = self.make_session(patterns=("ligne", "losange"))
        client, _ = self.join(code)
        me = client.get("/api/me").get_json()
        self.assertEqual(me["modules"], ["Les boucles"])
        self.assertTrue(all(t["module"] == "Les boucles" for t in me["tasks"]))
        self.assertEqual(client.get("/api/task/ligne").get_json()["module"],
                         "Les boucles")

    def test_session_page_names_its_modules(self):
        session_id, _ = self.make_session(patterns=("ligne", "bug_borne"))
        html = self.admin.get("/admin/sessions/%d" % session_id) \
                         .get_data(as_text=True)
        self.assertIn("Les boucles", html)

    def test_the_old_subtitle_is_gone_from_every_page(self):
        session_id, code = self.make_session(patterns=("ligne",))
        client, _ = self.join(code)
        pages = [self.app.test_client().get("/"),
                 client.get("/exercice"),
                 self.admin.get("/admin/"),
                 self.admin.get("/admin/sessions/%d" % session_id)]
        for page in pages:
            html = page.get_data(as_text=True)
            self.assertNotIn("motifs en C", html)
            self.assertNotIn("Atelier&nbsp;Algo", html)

    def test_debug_shows_both_outputs_and_hides_nothing(self):
        _, code = self.make_session(patterns=("bug_accolades",))
        client, _ = self.join(code)
        task = client.get("/api/task/bug_accolades").get_json()
        self.assertEqual(task["mode"], "debug")
        n = task["params"]["n"]
        # Ce qui etait voulu : n lignes d'une etoile. Ce qui sort : une ligne.
        self.assertEqual(task["target"], ["*"] * n)
        self.assertEqual(task["actual"], ["*" * n])
        self.assertEqual(len(task["blanks"][0]["options"]), 4)
        # Le bon diagnostic n'est pas signale dans la charge utile.
        self.assertNotIn("note", json.dumps(task))
        self.assertNotIn("ref", task)

    def test_debug_accepts_only_the_right_cause(self):
        _, code = self.make_session(patterns=("bug_borne",))
        client, _ = self.join(code)
        mauvaise = next(o for o in ex.PATTERNS["bug_borne"].blanks["cause"][1]
                        if o.id != ex.PATTERNS["bug_borne"].ref["cause"])

        res = client.post("/api/task/bug_borne/check",
                          json={"selection": {"cause": mauvaise.id}}).get_json()
        self.assertFalse(res["ok"])
        self.assertEqual(res["note"], mauvaise.note)   # retour cible

        res = client.post("/api/task/bug_borne/check",
                          json={"selection": {"cause": "a"}}).get_json()
        self.assertTrue(res["ok"])
        self.assertTrue(res["first_time"])
        self.assertIn("Exact", res["note"])

    def test_debug_without_a_choice_is_not_an_attempt(self):
        _, code = self.make_session(patterns=("bug_reinit",))
        client, _ = self.join(code)
        res = client.post("/api/task/bug_reinit/check",
                          json={"selection": {"cause": "zzz"}}).get_json()
        self.assertFalse(res["complete"])
        self.assertEqual(client.get("/api/task/bug_reinit")
                         .get_json()["attempts"], 0)

    def test_every_debug_exercise_has_a_visible_gap(self):
        """Sans écart entre l'attendu et l'obtenu, l'exercice n'a pas de sens."""
        for key, pattern in ex.PATTERNS.items():
            if pattern.mode != "debug":
                continue
            for params in tirages(pattern):
                with self.subTest(exercice=key, params=params):
                    self.assertNotEqual(ex.target_rows(key, params),
                                        ex.broken_rows(key, params))

    def test_debug_titles_do_not_give_the_answer_away(self):
        """Le nom du défaut ne doit jamais descendre jusqu'à l'élève."""
        _, code = self.make_session(
            patterns=tuple(k for k in ex.ALL_KEYS
                           if ex.PATTERNS[k].mode == "debug"))
        client, _ = self.join(code)
        for key in ex.ALL_KEYS:
            pattern = ex.PATTERNS[key]
            if pattern.mode != "debug":
                continue
            with self.subTest(exercice=key):
                self.assertTrue(pattern.teacher_note)
                envoye = json.dumps(client.get("/api/task/" + key).get_json())
                self.assertNotIn(pattern.teacher_note, envoye)
                self.assertNotIn("Défaut", envoye)

    def test_teacher_sees_the_defect_when_composing(self):
        page = self.admin.get("/admin/").get_data(as_text=True)
        for key in ex.ALL_KEYS:
            pattern = ex.PATTERNS[key]
            if pattern.mode == "debug":
                with self.subTest(exercice=key):
                    self.assertIn(str(escape(pattern.teacher_note)), page)

    def test_every_debug_option_carries_an_explanation(self):
        for key, pattern in ex.PATTERNS.items():
            if pattern.mode != "debug":
                continue
            for option in pattern.blanks["cause"][1]:
                with self.subTest(exercice=key, choix=option.id):
                    self.assertTrue(option.note.strip(), option.c)

    def test_exam_page_uses_no_native_dialog(self):
        """Un dialogue natif fait perdre le focus à la page.

        La surveillance le compterait comme une sortie de fenêtre, et
        l'élève serait pénalisé pour avoir cliqué sur « Remettre ma copie ».
        """
        source = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "atelier", "static", "js", "exercise.js")
        with open(source, encoding="utf-8") as fh:
            lignes = [l for l in fh if not l.strip().startswith("//")]
        for appel in ("window.confirm", "window.alert", "window.prompt"):
            with self.subTest(appel=appel):
                self.assertFalse([l for l in lignes if appel in l], appel)

    def test_student_receives_the_difficulty_of_each_exercise(self):
        _, code = self.make_session(patterns=("ligne", "losange"))
        client, _ = self.join(code)
        me = client.get("/api/me").get_json()
        niveaux = {t["key"]: (t["level"], t["level_name"]) for t in me["tasks"]}
        self.assertEqual(niveaux["ligne"], (1, "Découverte"))
        self.assertEqual(niveaux["losange"], (4, "Avancé"))
        task = client.get("/api/task/losange").get_json()
        self.assertEqual(task["level_name"], "Avancé")

    def test_unknown_pattern_is_404(self):
        _, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        self.assertEqual(client.get("/api/task/losange").status_code, 404)
        self.assertEqual(client.post("/api/task/carre_magique/check",
                                     json={"selection": {}}).status_code, 404)


class QcmTest(unittest.TestCase):
    """Chapitre QCM : import Excel, sous-modules, réponse de l'élève."""

    EN_TETE = ("Question", "Réponse A", "Réponse B", "Réponse C", "Réponse D",
               "Bonne réponse", "Explication", "Niveau")

    QUESTIONS = (
        ("Que fait `git clone` ?", "Copie un dépôt distant en local",
         "Envoie vos commits", "Crée une branche", "Efface l'historique",
         "A", "C'est la première commande du cycle.", 1),
        ("Que fait `git push` ?", "Crée un dépôt",
         "Envoie les commits locaux au dépôt distant", "Annule un commit",
         "Liste les branches", "B", "", 3),
    )

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({
            "TESTING": True, "DATABASE": self.path, "SECRET_KEY": "test",
            "ADMIN_USER": "prof", "ADMIN_PASSWORD": "secret",
        })
        self.admin = self.app.test_client()
        self.admin.post("/admin/login",
                        data={"username": "prof", "password": "secret"})

    def tearDown(self):
        # Le registre est un état de processus : un module importé par un
        # test suivrait les suivants si on ne le vidait pas. On repart du
        # catalogue livré, sans relire la base — elle va disparaître.
        ex.refresh([])
        qcm._loaded = None
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    # -- utilitaires -------------------------------------------------------

    def workbook(self, rows=None, header=None):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.append(header if header is not None else self.EN_TETE)
        for row in (self.QUESTIONS if rows is None else rows):
            sheet.append(row)
        buffer = io.BytesIO()
        book.save(buffer)
        return buffer.getvalue()

    def upload(self, data=None, title="Git : les bases", summary="",
               filename="git.xlsx"):
        return self.admin.post(
            "/admin/qcm",
            data={"title": title, "summary": summary,
                  "workbook": (io.BytesIO(self.workbook() if data is None
                                          else data), filename)},
            content_type="multipart/form-data",
        )

    def refusal(self, response):
        """Le message d'erreur d'un import refusé, tel que l'enseignant le lit."""
        location = response.headers["Location"]
        self.assertIn("error=", location)
        return urllib.parse.unquote_plus(location.split("error=")[-1])

    def session_on(self, keys):
        resp = self.admin.post("/admin/sessions",
                               data={"title": "TP QCM", "patterns": list(keys)})
        session_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        self.admin.post("/admin/sessions/%d/open" % session_id)
        html = self.admin.get("/admin/sessions/%d" % session_id) \
                         .get_data(as_text=True)
        code = html.split('class="joincode mono">')[1].split("<")[0].strip()
        client = self.app.test_client()
        client.post("/join", data={"first_name": "Ada", "last_name": "Lovelace",
                                   "code": code})
        return session_id, client

    # -- le module livré ---------------------------------------------------

    def test_the_qcm_chapter_ships_with_a_docker_module(self):
        chapitre = [c for c in ex.CHAPTERS if c.key == ex.QCM_CHAPTER_KEY]
        self.assertEqual(len(chapitre), 1)
        self.assertIn("qcm_docker", [m.key for m in chapitre[0].modules])
        module = ex.MODULE_BY_KEY["qcm_docker"]
        self.assertTrue(module.keys)
        for key in module.keys:
            with self.subTest(question=key):
                pattern = ex.PATTERNS[key]
                self.assertEqual(pattern.mode, "qcm")
                self.assertEqual(len(pattern.blanks["choix"][1]), 4)
                self.assertEqual(ex.answer_space(key), 4)

    def test_every_question_has_exactly_one_right_answer(self):
        for key in ex.ALL_KEYS:
            pattern = ex.PATTERNS[key]
            if pattern.mode != "qcm":
                continue
            with self.subTest(question=key):
                options = pattern.blanks["choix"][1]
                justes = [o for o in options if o.id == pattern.ref["choix"]]
                self.assertEqual(len(justes), 1)
                # Quatre propositions distinctes : deux identiques rendraient
                # une réponse juste indiscernable d'une fausse.
                self.assertEqual(len({o.c for o in options}), 4)

    def test_a_wrong_choice_never_reveals_the_answer(self):
        """Commenter une erreur reviendrait à donner la réponse."""
        for key in ex.MODULE_BY_KEY["qcm_docker"].keys:
            pattern = ex.PATTERNS[key]
            for option in pattern.blanks["choix"][1]:
                if option.id != pattern.ref["choix"]:
                    with self.subTest(question=key, choix=option.id):
                        self.assertEqual(option.note, "")

    # -- import ------------------------------------------------------------

    def test_an_import_creates_a_new_sub_module(self):
        self.upload(summary="Cloner, committer, pousser.")
        module = ex.MODULE_BY_KEY["git-les-bases"]
        self.assertEqual(module.title, "Git : les bases")
        self.assertEqual(module.summary, "Cloner, committer, pousser.")
        self.assertEqual(len(module.keys), 2)
        # Le niveau du module résume celui de ses questions : 1 et 3 -> 2.
        self.assertEqual(module.level, 2)
        self.assertEqual(ex.chapter_of(module.keys[0]).key, ex.QCM_CHAPTER_KEY)

        question = ex.PATTERNS[module.keys[0]]
        self.assertEqual(question.name, "Q1")
        self.assertEqual(question.brief, "Que fait `git clone` ?")
        self.assertEqual(question.level, 1)
        juste = [o for o in question.blanks["choix"][1]
                 if o.id == question.ref["choix"]][0]
        self.assertEqual(juste.c, "Copie un dépôt distant en local")

    def test_the_imported_module_appears_in_the_catalogue(self):
        self.upload()
        html = self.admin.get("/admin/").get_data(as_text=True)
        self.assertIn("Git : les bases", html)
        self.assertIn('data-module="git-les-bases"', html)
        self.assertIn('data-detail="qcm_git_les_bases_001"', html)

    def test_two_imports_of_the_same_title_keep_both(self):
        self.upload()
        self.upload()
        cles = [m.key for m in ex.MODULES]
        self.assertIn("git-les-bases", cles)
        self.assertIn("git-les-bases-2", cles)
        # Les clés de question restent uniques : le registre les refuserait.
        self.assertEqual(len(ex.ALL_KEYS), len(set(ex.ALL_KEYS)))

    def test_the_headers_are_read_without_case_or_accents(self):
        entete = ("QUESTION", "reponse a", "Reponse B", "réponse c",
                  "RÉPONSE D", "bonne reponse", "explication", "niveau")
        self.upload(data=self.workbook(header=entete))
        self.assertIn("git-les-bases", [m.key for m in ex.MODULES])

    def test_the_answer_may_be_a_letter_or_a_number(self):
        lignes = (("Q1 ?", "a", "b", "c", "d", "C", "", 2),
                  ("Q2 ?", "a", "b", "c", "d", "2", "", 2))
        self.upload(data=self.workbook(rows=lignes))
        module = ex.MODULE_BY_KEY["git-les-bases"]
        self.assertEqual(ex.PATTERNS[module.keys[0]].ref["choix"], "c2")
        self.assertEqual(ex.PATTERNS[module.keys[1]].ref["choix"], "c1")

    def test_blank_rows_are_ignored(self):
        lignes = (("Q1 ?", "a", "b", "c", "d", "A", "", 2),
                  (None, None, None, None, None, None, None, None),
                  ("Q2 ?", "a", "b", "c", "d", "B", "", 2))
        self.upload(data=self.workbook(rows=lignes))
        self.assertEqual(len(ex.MODULE_BY_KEY["git-les-bases"].keys), 2)

    def test_a_refused_workbook_says_what_is_wrong(self):
        cas = [
            (self.workbook(header=("Question", "Réponse A", "Réponse B",
                                   "Réponse C", "Bonne réponse")),
             "Réponse D"),
            (self.workbook(rows=(("Q ?", "a", "b", "c", "d", "Z", "", 2),)),
             "A, B, C ou D"),
            (self.workbook(rows=(("Q ?", "a", "", "c", "d", "A", "", 2),)),
             "proposition B vide"),
            (self.workbook(rows=(("Q ?", "a", "a", "c", "d", "A", "", 2),)),
             "identiques"),
            (self.workbook(rows=(("", "a", "b", "c", "d", "A", "", 2),)),
             "question est vide"),
            (self.workbook(rows=(("Q ?", "a", "b", "c", "d", "A", "", 9),)),
             "échelle 1 à 4"),
            (self.workbook(rows=()), "Aucune question"),
            (b"ceci n'est pas un classeur", "Fichier illisible"),
        ]
        for data, attendu in cas:
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, self.refusal(self.upload(data=data)))
        # Rien n'a été enregistré au passage.
        with self.app.app_context():
            self.assertEqual(qcm.imported(), [])

    def test_an_import_without_a_file_is_refused(self):
        resp = self.admin.post("/admin/qcm", data={"title": "X"},
                               content_type="multipart/form-data")
        self.assertIn("fichier", self.refusal(resp))

    def test_importing_requires_an_admin_session(self):
        anon = self.app.test_client()
        self.assertEqual(anon.post("/admin/qcm").status_code, 302)
        self.assertEqual(anon.get("/admin/qcm/modele.xlsx").status_code, 302)

    # -- le modèle ---------------------------------------------------------

    def test_the_model_can_be_imported_back(self):
        """Le format documenté et le format accepté ne peuvent pas diverger."""
        model = self.admin.get("/admin/qcm/modele.xlsx")
        self.assertEqual(model.status_code, 200)
        self.assertIn("modele-qcm.xlsx", model.headers["Content-Disposition"])

        self.upload(data=model.data, title="Docker relu",
                    filename="modele-qcm.xlsx")
        livre = ex.MODULE_BY_KEY["qcm_docker"]
        relu = ex.MODULE_BY_KEY["docker-relu"]
        self.assertEqual(len(relu.keys), len(livre.keys))
        for avant, apres in zip(livre.keys, relu.keys):
            with self.subTest(question=avant):
                a, b = ex.PATTERNS[avant], ex.PATTERNS[apres]
                self.assertEqual(a.brief, b.brief)
                self.assertEqual(a.level, b.level)
                self.assertEqual([o.c for o in a.blanks["choix"][1]],
                                 [o.c for o in b.blanks["choix"][1]])
                self.assertEqual(a.ref["choix"], b.ref["choix"])

    def test_the_application_runs_without_openpyxl(self):
        """L'hébergeur n'installe pas les paquets : l'absence doit se dire."""
        import builtins
        classeur = self.workbook()      # fabriqué tant qu'openpyxl est là
        vrai_import = builtins.__import__

        def sans_openpyxl(name, *args, **kwargs):
            if name == "openpyxl" or name.startswith("openpyxl."):
                raise ImportError("No module named 'openpyxl'")
            return vrai_import(name, *args, **kwargs)

        builtins.__import__ = sans_openpyxl
        try:
            # Les pages continuent de répondre : seul l'import est indisponible.
            self.assertEqual(self.admin.get("/admin/").status_code, 200)
            self.assertIn("pip install --user openpyxl",
                          self.refusal(self.upload(data=classeur)))
            modele = self.admin.get("/admin/qcm/modele.xlsx")
            self.assertIn("openpyxl",
                          urllib.parse.unquote_plus(modele.headers["Location"]))
        finally:
            builtins.__import__ = vrai_import

    # -- suppression -------------------------------------------------------

    def test_an_unused_module_can_be_deleted(self):
        self.upload()
        resp = self.admin.post("/admin/qcm/git-les-bases/delete")
        self.assertIn("ok=", resp.headers["Location"])
        self.assertNotIn("git-les-bases", [m.key for m in ex.MODULES])
        self.assertNotIn("qcm_git_les_bases_001", ex.PATTERNS)

    def test_a_module_used_by_a_session_is_not_deleted(self):
        """Supprimer ses questions viderait les copies qui les citent."""
        self.upload()
        keys = ex.MODULE_BY_KEY["git-les-bases"].keys
        self.session_on(keys)
        message = self.refusal(self.admin.post("/admin/qcm/git-les-bases/delete"))
        self.assertIn("TP QCM", message)
        self.assertIn("git-les-bases", [m.key for m in ex.MODULES])

    def test_deleting_an_unknown_module_says_so(self):
        self.assertIn("introuvable",
                      self.refusal(self.admin.post("/admin/qcm/néant/delete")))

    # -- côté élève --------------------------------------------------------

    def test_a_student_answers_a_question(self):
        self.upload()
        keys = ex.MODULE_BY_KEY["git-les-bases"].keys
        _, client = self.session_on(keys)

        task = client.get("/api/task/" + keys[0]).get_json()
        self.assertEqual(task["mode"], "qcm")
        self.assertEqual(task["question"], "Que fait `git clone` ?")
        self.assertEqual(task["module"], "Git : les bases")
        # Ni code ni sortie : la question se suffit.
        self.assertNotIn("code", task)
        self.assertNotIn("target", task)
        self.assertEqual(len(task["blanks"][0]["options"]), 4)

        juste = ex.PATTERNS[keys[0]].ref["choix"]
        faux = [o["id"] for o in task["blanks"][0]["options"]
                if o["id"] != juste][0]
        rate = client.post("/api/task/%s/check" % keys[0],
                           json={"selection": {"choix": faux}}).get_json()
        self.assertFalse(rate["ok"])
        self.assertEqual(rate["note"], "")       # la réponse n'est pas donnée
        self.assertEqual(rate["stakes"]["wrong"], 1)

        gagne = client.post("/api/task/%s/check" % keys[0],
                            json={"selection": {"choix": juste}}).get_json()
        self.assertTrue(gagne["ok"])
        self.assertIn("première commande", gagne["note"])
        # Quatre propositions, trois fausses : un tiers de 10 points.
        self.assertEqual(gagne["progress"]["score"], 6.67)

    def test_the_options_are_shuffled_per_student(self):
        """Deux voisins n'ont pas les propositions dans le même ordre."""
        self.upload()
        key = ex.MODULE_BY_KEY["git-les-bases"].keys[0]
        session_id, first = self.session_on([key])
        html = self.admin.get("/admin/sessions/%d" % session_id) \
                         .get_data(as_text=True)
        code = html.split('class="joincode mono">')[1].split("<")[0].strip()
        second = self.app.test_client()
        second.post("/join", data={"first_name": "Grace", "last_name": "Hopper",
                                   "code": code})
        ordres = [[o["id"] for o in client.get("/api/task/" + key)
                                          .get_json()["blanks"][0]["options"]]
                  for client in (first, second)]
        self.assertNotEqual(ordres[0], ordres[1])
        self.assertEqual(sorted(ordres[0]), sorted(ordres[1]))

    def test_no_answer_chosen_is_not_an_attempt(self):
        self.upload()
        key = ex.MODULE_BY_KEY["git-les-bases"].keys[0]
        _, client = self.session_on([key])
        res = client.post("/api/task/%s/check" % key,
                          json={"selection": {}}).get_json()
        self.assertFalse(res["complete"])
        self.assertIn("réponse", res["message"])
        self.assertEqual(client.get("/api/task/" + key)
                               .get_json()["stakes"]["wrong"], 0)

    def test_the_api_never_sends_the_right_answer_before_it_is_found(self):
        self.upload()
        key = ex.MODULE_BY_KEY["git-les-bases"].keys[0]
        _, client = self.session_on([key])
        envoye = json.dumps(client.get("/api/task/" + key).get_json())
        self.assertNotIn("choix", json.loads(envoye).get("selection", {}))
        self.assertNotIn("ref", envoye)
        self.assertNotIn("première commande", envoye)   # l'explication

    def test_a_qcm_session_is_proctored_like_any_other(self):
        """Un QCM se passe sous les mêmes règles : plein écran et surveillance."""
        self.upload()
        keys = ex.MODULE_BY_KEY["git-les-bases"].keys
        _, client = self.session_on(keys)
        page = client.get("/exercice").get_data(as_text=True)
        self.assertIn("plein écran", page)
        self.assertIn("js/proctor.js", page)
        res = client.post("/api/incident", json={"kind": "blur"}).get_json()
        self.assertEqual(res["ordinal"], 1)

    def test_a_session_may_mix_a_qcm_and_c_exercises(self):
        self.upload()
        keys = [ex.MODULE_BY_KEY["git-les-bases"].keys[0], "carre"]
        _, client = self.session_on(keys)
        me = client.get("/api/me").get_json()
        self.assertEqual(me["modules"], ["Les boucles", "Git : les bases"])
        self.assertEqual(me["progress"]["total"], 2)

    def test_the_report_situates_short_question_names(self):
        """« Q1 » ne dit rien hors de son module : on le nomme si besoin."""
        self.upload()
        keys = [ex.MODULE_BY_KEY["git-les-bases"].keys[0], "carre"]
        _, client = self.session_on(keys)
        client.post("/api/finish")
        page = client.get("/termine").get_data(as_text=True)
        self.assertIn("Git : les bases · Q1", page)

        # Un seul module : le préfixe n'apporterait que du bruit.
        _, seul = self.session_on([ex.MODULE_BY_KEY["git-les-bases"].keys[0]])
        seul.post("/api/finish")
        page = seul.get("/termine").get_data(as_text=True)
        self.assertNotIn("Git : les bases · Q1", page)

    # -- rechargement entre processus --------------------------------------

    def test_another_process_picks_up_the_import(self):
        """Un import fait ailleurs doit apparaître à la requête suivante."""
        self.upload()
        autre = create_app({
            "TESTING": True, "DATABASE": self.path, "SECRET_KEY": "test",
            "ADMIN_USER": "prof", "ADMIN_PASSWORD": "secret",
        })
        # On simule un processus resté sur le catalogue d'avant l'import :
        # son empreinte est celle d'une base sans aucun QCM importé.
        ex.refresh([])
        qcm._loaded = (0, 0, 0)
        self.assertNotIn("git-les-bases", [m.key for m in ex.MODULES])

        client = autre.test_client()
        client.post("/admin/login",
                    data={"username": "prof", "password": "secret"})
        client.get("/admin/")
        self.assertIn("git-les-bases", [m.key for m in ex.MODULES])


class ExamModeTest(unittest.TestCase):
    """Mode examen : l'eleve repond, et n'apprend rien de sa reussite.

    Les tests portent sur ce que le serveur envoie, pas sur l'habillage :
    une case cachee en CSS resterait lisible dans la reponse JSON, et
    l'eleve n'a pas besoin de la page pour interroger l'API.
    """

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({
            "TESTING": True, "DATABASE": self.path, "SECRET_KEY": "test",
            "ADMIN_USER": "prof", "ADMIN_PASSWORD": "secret",
        })
        self.admin = self.app.test_client()
        self.admin.post("/admin/login",
                        data={"username": "prof", "password": "secret"})
        # Les quatre modes du catalogue : compléter, prédire, diagnostiquer,
        # répondre à un QCM. Chacun a sa propre réponse à cacher.
        self.keys = [un_exercice(m) for m in
                     ("complete", "predict", "debug", "qcm")]

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    # -- utilitaires -------------------------------------------------------

    def session_on(self, exam=True, patterns=None):
        data = {"title": "Épreuve", "patterns": patterns or self.keys}
        if exam:
            data["exam_mode"] = "1"
        resp = self.admin.post("/admin/sessions", data=data)
        session_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        self.admin.post("/admin/sessions/%d/open" % session_id)
        page = self.admin.get("/admin/sessions/%d" % session_id)
        code = page.get_data(as_text=True) \
                   .split('class="joincode mono">')[1].split("<")[0].strip()
        return session_id, code

    def join(self, code, first="Ada", last="Lovelace"):
        client = self.app.test_client()
        client.post("/join", data={"first_name": first, "last_name": last,
                                   "code": code})
        return client

    def answer(self, client, key, right=True):
        """Repond a un exercice, juste ou faux, quel que soit son mode."""
        task = client.get("/api/task/" + key).get_json()
        pattern = ex.PATTERNS[key]
        if pattern.mode == "predict":
            lignes = ex.target_rows(key, task["params"])
            body = {"answer": "\n".join(lignes) if right else "n'importe quoi"}
        elif right:
            body = {"selection": dict(pattern.ref)}
        else:
            blank_id = next(iter(pattern.blanks))
            faux = [o.id for o in pattern.blanks[blank_id][1]
                    if o.id != pattern.ref[blank_id]][0]
            body = {"selection": dict(pattern.ref, **{blank_id: faux})}
        return client.post("/api/task/%s/check" % key, json=body).get_json()

    def solved_count(self, session_id):
        """Exercices reussis, tels que l'enseignant les voit."""
        live = self.admin.get(
            "/admin/api/sessions/%d/live" % session_id).get_json()
        return live["students"][0]["solved"]

    # -- ce que l'eleve ne doit pas apprendre ------------------------------

    # Tout ce qui, dans une reponse du serveur, dirait « juste » ou « faux ».
    VERDICTS = ("ok", "first_time", "diff", "target", "note",
                "count_mismatch", "stakes")

    def test_no_answer_ever_carries_a_verdict(self):
        """Ni juste, ni faux, ni la cible, ni la valeur de l'exercice."""
        _, code = self.session_on()
        eleve = self.join(code)
        for key in self.keys:
            for right in (True, False):
                with self.subTest(pattern=key, juste=right):
                    res = self.answer(eleve, key, right=right)
                    self.assertTrue(res["complete"])
                    self.assertTrue(res["exam"])
                    for champ in self.VERDICTS:
                        self.assertNotIn(champ, res)

    def test_a_task_never_says_it_is_solved(self):
        _, code = self.session_on()
        eleve = self.join(code)
        for key in self.keys:
            self.answer(eleve, key)
        for key in self.keys:
            with self.subTest(pattern=key):
                task = eleve.get("/api/task/" + key).get_json()
                self.assertIsNone(task["solved"])
                self.assertIsNone(task["stakes"])
                self.assertTrue(task["answered"])
                self.assertTrue(task["exam"])
        for task in eleve.get("/api/me").get_json()["tasks"]:
            self.assertIsNone(task["solved"])
            self.assertIsNone(task["stakes"])
            self.assertTrue(task["answered"])

    def test_the_expected_output_of_a_prediction_stays_hidden(self):
        """En mode ordinaire, trouver devoile la cible. En examen, jamais."""
        key = un_exercice("predict")
        _, code = self.session_on(patterns=[key])
        eleve = self.join(code)
        self.assertIsNone(self.answer(eleve, key).get("target"))
        self.assertIsNone(eleve.get("/api/task/" + key).get_json()["target"])

    def test_the_progress_counts_answers_and_hides_the_score(self):
        _, code = self.session_on()
        eleve = self.join(code)
        self.answer(eleve, self.keys[0])
        progress = eleve.get("/api/me").get_json()["progress"]
        self.assertTrue(progress["exam"])
        self.assertEqual(progress["answered"], 1)
        self.assertEqual(progress["total"], len(self.keys))
        self.assertIsNone(progress["score"])
        self.assertIsNone(progress["solved"])
        self.assertIsNone(progress["lost"])

    def test_the_penalties_stay_visible(self):
        """L'eleve voit ce que ses sorties lui coutent : c'etait annonce."""
        _, code = self.session_on()
        eleve = self.join(code)
        for _ in range(2):
            sortie = eleve.post("/api/incident", json={"kind": "blur"})
        data = sortie.get_json()
        self.assertEqual(data["ordinal"], 2)
        self.assertEqual(data["total_penalty"], 2.0)
        self.assertEqual(data["progress"]["penalty"], 2.0)
        self.assertEqual(data["progress"]["exits"], 2)

    def test_the_final_page_gives_no_result(self):
        _, code = self.session_on()
        eleve = self.join(code)
        self.answer(eleve, self.keys[0])
        eleve.post("/api/incident", json={"kind": "blur"})
        eleve.post("/api/finish")
        page = eleve.get("/termine").get_data(as_text=True)
        self.assertIn("Questions traitées", page)
        self.assertIn("Pénalités", page)          # les sorties, elles, restent
        self.assertNotIn("/ 20", page)
        self.assertNotIn("réussi", page)
        self.assertNotIn("Détail par motif", page)

    # -- ce que l'enseignant garde -----------------------------------------

    def test_the_teacher_keeps_the_whole_truth(self):
        """Le mode examen cache a l'eleve, jamais a l'enseignant."""
        session_id, code = self.session_on()
        eleve = self.join(code)
        for key in self.keys:
            self.answer(eleve, key, right=False)
            self.answer(eleve, key, right=True)

        live = self.admin.get(
            "/admin/api/sessions/%d/live" % session_id).get_json()
        self.assertTrue(live["exam_mode"])
        copie = live["students"][0]
        self.assertEqual(copie["solved"], len(self.keys))
        # Les essais manques sont comptes — l'enseignant les lit — mais ne
        # retirent rien : la copie vaut 20, et rien n'est « perdu ».
        self.assertEqual(copie["wrong"], len(self.keys))
        self.assertEqual(copie["score"], 20.0)
        self.assertEqual(copie["lost"], 0.0)

        # Et la note est figee a la cloture, comme pour toute session.
        self.admin.post("/admin/sessions/%d/close" % session_id)
        csv_export = self.admin.get(
            "/admin/sessions/%d/export.csv" % session_id).get_data(as_text=True)
        self.assertIn("LOVELACE Ada", csv_export)

    # -- ce qu'un essai manque coute en examen : rien ---------------------

    def test_a_wrong_attempt_costs_nothing(self):
        """Sans retour, l'eleve ne peut pas chercher : on ne le sanctionne pas.

        En entrainement, epuiser les reponses ramene l'exercice a zero — la
        regle existe pour qu'on ne trouve pas la bonne en tatonnant. En
        examen l'application ne dit plus quand on tombe juste : la sanction
        n'a plus de cible.
        """
        key = un_exercice("qcm")
        session_id, code = self.session_on(patterns=[key])
        eleve = self.join(code)
        for _ in range(3):
            self.answer(eleve, key, right=False)
        self.answer(eleve, key, right=True)

        copie = self.admin.get(
            "/admin/api/sessions/%d/live" % session_id).get_json()["students"][0]
        self.assertEqual(copie["wrong"], 3)     # comptes pour l'enseignant
        self.assertEqual(copie["lost"], 0.0)    # mais gratuits
        self.assertEqual(copie["score"], 20.0)

        # Et la note figee a la cloture suit la meme regle.
        self.admin.post("/admin/sessions/%d/close" % session_id)
        fige = self.admin.get(
            "/admin/api/sessions/%d/live" % session_id).get_json()["students"][0]
        self.assertEqual(fige["score"], 20.0)

    def test_the_same_copy_is_punished_in_training(self):
        """Le contre-exemple : hors examen, ces trois essais coutent tout."""
        key = un_exercice("qcm")
        session_id, code = self.session_on(exam=False, patterns=[key])
        eleve = self.join(code)
        for _ in range(3):
            self.answer(eleve, key, right=False)
        self.answer(eleve, key, right=True)

        copie = self.admin.get(
            "/admin/api/sessions/%d/live" % session_id).get_json()["students"][0]
        self.assertEqual(copie["wrong"], 3)
        self.assertEqual(copie["score"], 0.0)   # quatre reponses, trois ratees

    def test_the_copy_is_judged_on_the_answer_it_holds(self):
        """Trouver puis changer d'avis : c'est la derniere reponse qui compte.

        Sans cela, un essai manque gratuit et une reussite acquise pour
        toujours se combineraient en une faille : essayer les quatre
        propositions garantirait le point.
        """
        for mode in ("qcm", "debug", "complete", "predict"):
            key = un_exercice(mode)
            session_id, code = self.session_on(patterns=[key])
            eleve = self.join(code, last="Mode%s" % mode)
            with self.subTest(mode=mode):
                self.answer(eleve, key, right=True)
                self.assertEqual(self.solved_count(session_id), 1)
                self.answer(eleve, key, right=False)
                self.assertEqual(self.solved_count(session_id), 0)
                # Et l'on peut revenir : rien n'est definitif avant la remise.
                self.answer(eleve, key, right=True)
                self.assertEqual(self.solved_count(session_id), 1)

    def test_exhausting_the_options_earns_nothing_by_itself(self):
        """Passer en revue les quatre propositions ne garantit pas le point."""
        key = un_exercice("qcm")
        session_id, code = self.session_on(patterns=[key])
        eleve = self.join(code)
        pattern = ex.PATTERNS[key]
        blank_id = next(iter(pattern.blanks))
        # Toutes les propositions, dans l'ordre, la bonne au milieu.
        for option in pattern.blanks[blank_id][1]:
            eleve.post("/api/task/%s/check" % key,
                       json={"selection": {blank_id: option.id}})
        derniere = pattern.blanks[blank_id][1][-1].id
        attendu = 1 if derniere == pattern.ref[blank_id] else 0
        self.assertEqual(self.solved_count(session_id), attendu)

    def test_an_emptied_answer_is_no_longer_acquired(self):
        """Vider ses menus retire l'acquis : la copie ne porte plus rien."""
        key = un_exercice("complete")
        session_id, code = self.session_on(patterns=[key])
        eleve = self.join(code)
        self.answer(eleve, key, right=True)
        self.assertEqual(self.solved_count(session_id), 1)
        vide = eleve.post("/api/task/%s/check" % key,
                          json={"selection": {}}).get_json()
        self.assertFalse(vide["complete"])
        self.assertEqual(self.solved_count(session_id), 0)

    def test_a_training_answer_stays_acquired(self):
        """Hors examen, un exercice trouve reste trouve : on peut y revenir."""
        key = un_exercice("qcm")
        session_id, code = self.session_on(exam=False, patterns=[key])
        eleve = self.join(code)
        self.answer(eleve, key, right=True)
        self.answer(eleve, key, right=False)
        self.assertEqual(self.solved_count(session_id), 1)

    def test_the_session_view_says_it_is_an_exam(self):
        session_id, _ = self.session_on()
        page = self.admin.get("/admin/sessions/%d" % session_id)
        self.assertIn("mode examen", page.get_data(as_text=True))

    # -- et sans la case cochee, rien ne change ----------------------------

    def test_an_ordinary_session_is_untouched(self):
        _, code = self.session_on(exam=False)
        eleve = self.join(code)
        self.assertFalse(eleve.get("/api/me").get_json()["exam"])
        for key in self.keys:
            with self.subTest(pattern=key):
                res = self.answer(eleve, key)
                self.assertTrue(res["ok"])
                self.assertTrue(res["first_time"])
                self.assertFalse(res["exam"])
                self.assertIsNotNone(res["stakes"])
                self.assertIsNotNone(res["progress"]["score"])
                task = eleve.get("/api/task/" + key).get_json()
                self.assertTrue(task["solved"])
        eleve.post("/api/finish")
        self.assertIn("/ 20", eleve.get("/termine").get_data(as_text=True))

    def test_exam_mode_is_off_unless_asked(self):
        _, code = self.session_on(exam=False)
        eleve = self.join(code)
        progress = eleve.get("/api/me").get_json()["progress"]
        self.assertFalse(progress["exam"])
        self.assertEqual(progress["score"], 0.0)


class AccountsTest(unittest.TestCase):
    """Comptes enseignants : l'administrateur les cree, eux ne peuvent pas."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({
            "TESTING": True, "DATABASE": self.path, "SECRET_KEY": "test",
            "ADMIN_USER": "prof", "ADMIN_PASSWORD": "secret",
        })
        self.admin = self.app.test_client()
        self.admin.post("/admin/login",
                        data={"username": "prof", "password": "secret"})

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    # -- utilitaires -------------------------------------------------------

    def create(self, username="c.durand", password="motdepasse"):
        return self.admin.post("/admin/comptes",
                               data={"username": username,
                                     "password": password})

    def refusal(self, response):
        location = response.headers["Location"]
        self.assertIn("error=", location)
        return urllib.parse.unquote_plus(location.split("error=")[1])

    def signed_in(self, username="c.durand", password="motdepasse"):
        client = self.app.test_client()
        resp = client.post("/admin/login",
                           data={"username": username, "password": password})
        return client, resp

    def rows(self, sql, args=()):
        import sqlite3
        conn = sqlite3.connect(self.path)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    # -- ce qu'un profil peut faire ----------------------------------------

    def test_a_profile_runs_sessions_like_the_administrator(self):
        self.create()
        prof2, resp = self.signed_in()
        self.assertEqual(resp.headers["Location"], "/admin/")

        created = prof2.post("/admin/sessions",
                             data={"title": "TP de C. Durand",
                                   "patterns": ["carre"]})
        session_id = int(created.headers["Location"].rstrip("/").split("/")[-1])
        self.assertEqual(prof2.post("/admin/sessions/%d/open" % session_id)
                         .status_code, 302)
        self.assertEqual(prof2.get("/admin/sessions/%d" % session_id)
                         .status_code, 200)
        self.assertEqual(prof2.get("/admin/api/sessions/%d/live" % session_id)
                         .status_code, 200)
        self.assertEqual(prof2.get("/admin/sessions/%d/export.csv" % session_id)
                         .status_code, 200)
        self.assertEqual(prof2.get("/admin/historique").status_code, 200)

        # La session porte le nom de son auteur : nous sommes plusieurs.
        self.assertEqual(
            self.rows("SELECT created_by FROM session")[0][0], "c.durand")
        self.assertIn("c.durand",
                      self.admin.get("/admin/").get_data(as_text=True))

    # -- ce qu'un profil ne peut pas faire ---------------------------------

    def test_a_profile_cannot_touch_the_accounts(self):
        self.create()
        self.create("a.martin")
        victime = self.rows(
            "SELECT id FROM teacher WHERE username = 'a.martin'")[0][0]
        prof2, _ = self.signed_in()
        self.assertEqual(prof2.get("/admin/comptes").status_code, 403)
        self.assertEqual(prof2.post("/admin/comptes",
                                    data={"username": "intrus",
                                          "password": "motdepasse"}).status_code,
                         403)
        self.assertEqual(prof2.post("/admin/comptes/%d/password" % victime,
                                    data={"password": "autrechose"}).status_code,
                         403)
        self.assertEqual(prof2.post("/admin/comptes/%d/delete" % victime)
                         .status_code, 403)
        # Aucun compte cree, aucun mot de passe change, personne supprime.
        self.assertEqual(len(self.rows("SELECT id FROM teacher")), 2)
        self.assertIsNotNone(self.signed_in("a.martin")[1]
                             .headers.get("Location"))
        self.assertEqual(self.signed_in("a.martin")[1].headers["Location"],
                         "/admin/")
        # Et le lien vers les comptes ne lui est meme pas propose.
        self.assertNotIn("/admin/comptes",
                         prof2.get("/admin/").get_data(as_text=True))

    def test_the_accounts_page_needs_a_session_at_all(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/admin/comptes").status_code, 302)
        self.assertEqual(anon.post("/admin/comptes",
                                   data={"username": "intrus",
                                         "password": "motdepasse"}).status_code,
                         302)
        self.assertEqual(len(self.rows("SELECT id FROM teacher")), 0)

    # -- garde-fous a la creation ------------------------------------------

    def test_a_duplicate_identifier_is_refused(self):
        self.create()
        self.assertIn("déjà", self.refusal(self.create()))
        # Meme a la casse pres : deux « c.durand » seraient indiscernables.
        self.assertIn("déjà", self.refusal(self.create("C.Durand")))
        self.assertEqual(len(self.rows("SELECT id FROM teacher")), 1)

    def test_the_administrator_identifier_cannot_be_taken(self):
        self.assertIn("administrateur", self.refusal(self.create("prof")))
        self.assertIn("administrateur", self.refusal(self.create("PROF")))

    def test_a_short_password_is_refused(self):
        self.assertIn("caractères", self.refusal(self.create(password="court")))
        self.assertEqual(len(self.rows("SELECT id FROM teacher")), 0)

    def test_an_empty_identifier_is_refused(self):
        self.assertIn("obligatoire", self.refusal(self.create("   ")))

    def test_a_password_is_never_stored_in_clear(self):
        self.create(password="motdepasse")
        stored = self.rows("SELECT password_hash FROM teacher")[0][0]
        self.assertNotIn("motdepasse", stored)
        self.assertGreater(len(stored), 30)

    def test_a_wrong_password_opens_nothing(self):
        self.create()
        _, resp = self.signed_in(password="pas-le-bon")
        self.assertEqual(resp.status_code, 200)     # la page de connexion
        self.assertIn("incorrects", resp.get_data(as_text=True))

    # -- reinitialisation et suppression -----------------------------------

    def test_the_administrator_replaces_a_password(self):
        self.create()
        teacher_id = self.rows("SELECT id FROM teacher")[0][0]
        self.admin.post("/admin/comptes/%d/password" % teacher_id,
                        data={"password": "nouveau-mot"})
        self.assertEqual(self.signed_in(password="nouveau-mot")[1]
                         .headers["Location"], "/admin/")
        self.assertEqual(self.signed_in(password="motdepasse")[1].status_code,
                         200)
        court = self.admin.post("/admin/comptes/%d/password" % teacher_id,
                                data={"password": "court"})
        self.assertIn("caractères", self.refusal(court))

    def test_a_deleted_profile_cannot_sign_in_anymore(self):
        self.create()
        prof2, _ = self.signed_in()
        created = prof2.post("/admin/sessions",
                             data={"title": "TP", "patterns": ["carre"]})
        teacher_id = self.rows("SELECT id FROM teacher")[0][0]
        self.admin.post("/admin/comptes/%d/delete" % teacher_id)
        self.assertEqual(len(self.rows("SELECT id FROM teacher")), 0)
        self.assertEqual(self.signed_in()[1].status_code, 200)
        # Sa session reste : elle porte les copies des eleves.
        self.assertEqual(len(self.rows("SELECT id FROM session")), 1)
        self.assertIsNotNone(created)

    def test_deleting_an_unknown_account_says_so(self):
        self.assertIn("introuvable",
                      self.refusal(self.admin.post("/admin/comptes/404/delete")))

    def test_the_environment_administrator_is_not_in_the_list(self):
        self.create()
        page = self.admin.get("/admin/comptes").get_data(as_text=True)
        self.assertIn("c.durand", page)
        self.assertIn("ATELIER_ADMIN_USER", page)
        self.assertNotIn("<td class=\"strong\">prof</td>", page)


class MigrationTest(unittest.TestCase):
    """Une base deja deployee doit survivre a l'ajout d'une colonne."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.remove(self.path)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def _old_database(self):
        """Le schéma courant, privé des colonnes ajoutées après coup."""
        import sqlite3
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "atelier", "schema.sql"),
                  encoding="utf-8") as fh:
            schema = fh.read()

        # Le rattrapage se fait par (table, colonne) : on ne retire la ligne
        # que de la table concernée. Une même colonne peut exister dans deux
        # tables — `created_by` est sur `session` comme sur `teacher`.
        retirer = {(t, c) for t, c, _decl in db.ADDED_COLUMNS}
        table, gardees = None, []
        marqueur = "CREATE TABLE IF NOT EXISTS "
        for line in schema.splitlines():
            nu = line.strip()
            if nu.startswith(marqueur):
                table = nu[len(marqueur):].split("(")[0].strip()
            if (table, nu.split(" ")[0]) not in retirer:
                gardees.append(line)
        schema = "\n".join(gardees)

        conn = sqlite3.connect(self.path)
        conn.executescript(schema)
        conn.execute("""INSERT INTO session (code, title, patterns, created_at)
                        VALUES ('ABC123', 'ancienne', '["carre"]', '2026-01-01')""")
        conn.execute("""INSERT INTO student (session_id, first_name, last_name,
                                             token, joined_at)
                        VALUES (1, 'Ada', 'Lovelace', 'jeton', '2026-01-01')""")
        conn.execute("""INSERT INTO task (student_id, pattern_key, position,
                                          params, attempts, solved)
                        VALUES (1, 'carre', 0, '{"n": 4}', 5, 1)""")
        conn.commit()
        conn.close()

    def _columns(self, table="task"):
        import sqlite3
        conn = sqlite3.connect(self.path)
        try:
            return [row[1] for row in
                    conn.execute("PRAGMA table_info(%s)" % table)]
        finally:
            conn.close()

    def test_a_missing_column_is_added_without_losing_anything(self):
        self._old_database()
        self.assertNotIn("wrong_attempts", self._columns())

        app = create_app({"TESTING": True, "DATABASE": self.path,
                          "SECRET_KEY": "test", "ADMIN_USER": "prof",
                          "ADMIN_PASSWORD": "secret"})
        self.assertIn("wrong_attempts", self._columns())

        import sqlite3
        conn = sqlite3.connect(self.path)
        row = conn.execute(
            "SELECT attempts, solved, wrong_attempts FROM task").fetchone()
        conn.close()
        # Les copies d'avant ne sont pas sanctionnées rétroactivement.
        self.assertEqual(row, (5, 1, 0))

        # Idempotent : un deuxième démarrage ne rejoue pas l'ajout.
        create_app({"TESTING": True, "DATABASE": self.path,
                    "SECRET_KEY": "test", "ADMIN_USER": "prof",
                    "ADMIN_PASSWORD": "secret"})
        self.assertEqual(self._columns().count("wrong_attempts"), 1)
        self.assertIsNotNone(app)


    def test_the_session_columns_arrive_on_an_existing_base(self):
        """Une base d'avant le mode examen doit l'acquerir, sans rien perdre."""
        self._old_database()
        self.assertNotIn("exam_mode", self._columns("session"))
        self.assertNotIn("created_by", self._columns("session"))

        create_app({"TESTING": True, "DATABASE": self.path,
                    "SECRET_KEY": "test", "ADMIN_USER": "prof",
                    "ADMIN_PASSWORD": "secret"})
        self.assertIn("exam_mode", self._columns("session"))
        self.assertIn("created_by", self._columns("session"))

        import sqlite3
        conn = sqlite3.connect(self.path)
        row = conn.execute(
            "SELECT title, exam_mode, created_by FROM session").fetchone()
        conn.close()
        # Les sessions d'avant ne basculent pas en examen par surprise.
        self.assertEqual(row, ("ancienne", 0, ""))

    def test_the_accounts_table_appears_on_an_existing_base(self):
        """La table des comptes manque a une base d'avant : elle est creee."""
        import sqlite3
        self._old_database()
        # `_old_database` rejoue le schema courant : la table des comptes y
        # est. On la retire pour retrouver une base d'avant leur arrivee.
        conn = sqlite3.connect(self.path)
        conn.execute("DROP TABLE teacher")
        conn.commit()
        conn.close()
        self.assertEqual(self._columns("teacher"), [])

        app = create_app({"TESTING": True, "DATABASE": self.path,
                          "SECRET_KEY": "test", "ADMIN_USER": "prof",
                          "ADMIN_PASSWORD": "secret"})
        self.assertIn("password_hash", self._columns("teacher"))

        # Et l'administrateur peut y creer un compte des ce demarrage.
        client = app.test_client()
        client.post("/admin/login",
                    data={"username": "prof", "password": "secret"})
        resp = client.post("/admin/comptes", data={"username": "c.durand",
                                                   "password": "motdepasse"})
        self.assertIn("ok=", resp.headers["Location"])


class EnvFileTest(unittest.TestCase):
    """Le deploiement depose un .env : create_app doit le lire."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env_path = os.path.join(self.dir, ".env")
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, text):
        with open(self.env_path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_values_are_loaded(self):
        self.write("ATELIER_ADMIN_USER=prof\nATELIER_ADMIN_PASSWORD=motdepasse\n")
        os.environ.pop("ATELIER_ADMIN_USER", None)
        os.environ.pop("ATELIER_ADMIN_PASSWORD", None)
        loaded = load_env_file(self.env_path)
        self.assertEqual(sorted(loaded),
                         ["ATELIER_ADMIN_PASSWORD", "ATELIER_ADMIN_USER"])
        self.assertEqual(os.environ["ATELIER_ADMIN_USER"], "prof")

    def test_existing_environment_wins(self):
        self.write("ATELIER_ADMIN_USER=du-fichier\n")
        os.environ["ATELIER_ADMIN_USER"] = "de-l-environnement"
        self.assertEqual(load_env_file(self.env_path), [])
        self.assertEqual(os.environ["ATELIER_ADMIN_USER"], "de-l-environnement")

    def test_comments_blank_lines_and_quotes(self):
        self.write('# un commentaire\n\n'
                   'ATELIER_ADMIN_USER="entre guillemets"\n'
                   "ATELIER_ADMIN_PASSWORD='simples'\n"
                   'ligne_sans_egal\n')
        for name in ("ATELIER_ADMIN_USER", "ATELIER_ADMIN_PASSWORD"):
            os.environ.pop(name, None)
        load_env_file(self.env_path)
        self.assertEqual(os.environ["ATELIER_ADMIN_USER"], "entre guillemets")
        self.assertEqual(os.environ["ATELIER_ADMIN_PASSWORD"], "simples")

    def test_missing_file_is_not_an_error(self):
        self.assertEqual(load_env_file(os.path.join(self.dir, "absent")), [])

    def test_create_app_reads_the_file(self):
        self.write("ATELIER_SECRET_KEY=cle-venue-du-fichier\n"
                   "ATELIER_ADMIN_USER=prof\n"
                   "ATELIER_ADMIN_PASSWORD=secret\n")
        for name in ("ATELIER_SECRET_KEY", "ATELIER_ADMIN_USER",
                     "ATELIER_ADMIN_PASSWORD"):
            os.environ.pop(name, None)
        os.environ["ATELIER_ENV_FILE"] = self.env_path
        os.environ["ATELIER_DATABASE"] = os.path.join(self.dir, "t.sqlite")
        app = create_app()
        self.assertEqual(app.config["SECRET_KEY"], "cle-venue-du-fichier")
        self.assertEqual(app.config["ADMIN_USER"], "prof")

        # Et l'enseignant peut effectivement se connecter avec ces valeurs.
        client = app.test_client()
        resp = client.post("/admin/login",
                           data={"username": "prof", "password": "secret"})
        self.assertEqual(resp.headers["Location"], "/admin/")


class ScoringTest(unittest.TestCase):

    def test_penalty_table(self):
        self.assertEqual(scoring.penalty_for(1), 0.0)
        self.assertEqual(scoring.penalty_for(2), 2.0)
        self.assertEqual(scoring.penalty_for(3), 3.0)
        self.assertEqual(scoring.penalty_for(9), 3.0)

    def test_bounds(self):
        self.assertEqual(scoring.final_score([1.0] * 8, 8, 0), 20.0)
        self.assertEqual(scoring.final_score([], 8, 0), 0.0)
        self.assertEqual(scoring.final_score([1.0] * 4, 8, 20), 0.0)
        self.assertEqual(scoring.final_score([], 0, 0), 0.0)

    def test_a_failed_attempt_eats_a_share_of_the_exercise(self):
        """Quatre réponses possibles, trois fausses : un tiers par essai."""
        self.assertEqual(scoring.kept_share(4, 0), 1.0)
        self.assertAlmostEqual(scoring.kept_share(4, 1), 2 / 3)
        self.assertAlmostEqual(scoring.kept_share(4, 2), 1 / 3)
        self.assertEqual(scoring.kept_share(4, 3), 0.0)

    def test_the_share_follows_the_number_of_possible_answers(self):
        """Plus l'exercice offre de réponses, moins un essai coûte cher."""
        self.assertAlmostEqual(scoring.kept_share(16, 1), 14 / 15)
        self.assertEqual(scoring.kept_share(16, 15), 0.0)
        # Quinze réponses fausses au lieu de trois : l'essai coûte cinq
        # fois moins cher sur le même exercice.
        self.assertAlmostEqual(scoring.attempt_cost(8, 4),
                               5 * scoring.attempt_cost(8, 16))

    def test_trying_every_answer_earns_nothing(self):
        """Épuiser les réponses ramène l'exercice à zéro, jamais au-dessous."""
        for choices in (4, 16):
            for wrong in range(choices - 1, choices + 8):
                with self.subTest(choices=choices, wrong=wrong):
                    self.assertEqual(scoring.kept_share(choices, wrong), 0.0)

    def test_wrong_attempts_can_be_ignored_altogether(self):
        """Regime du mode examen : la reussite garde sa valeur pleine."""
        def quatre(_key):
            return 4

        taches = [{"pattern_key": "x", "wrong_attempts": 3, "solved": 1},
                  {"pattern_key": "x", "wrong_attempts": 0, "solved": 1},
                  {"pattern_key": "x", "wrong_attempts": 9, "solved": 0}]
        self.assertEqual(scoring.shares_of(taches, quatre), [0.0, 1.0])
        self.assertEqual(scoring.shares_of(taches, quatre, count_wrong=False),
                         [1.0, 1.0])
        # Un exercice jamais trouve ne rapporte rien dans les deux regimes.
        self.assertEqual(
            scoring.base_score(
                scoring.shares_of(taches, quatre, count_wrong=False), 3),
            round(20.0 * 2 / 3, 2))

    def test_the_cost_is_proportional_to_the_value_of_an_exercise(self):
        """Le même exercice coûte moins cher dans une session plus longue."""
        self.assertEqual(scoring.attempt_cost(4, 4), 5.0 / 3)
        self.assertEqual(scoring.attempt_cost(8, 4), 2.5 / 3)
        self.assertEqual(scoring.exercise_value(8), 2.5)
        self.assertEqual(scoring.exercise_value(0), 0.0)


class LinuxTest(unittest.TestCase):
    """Le chapitre Linux : des commandes, et leur vraie sortie.

    Les sorties attendues ci-dessous ont été relevées sur un vrai shell
    GNU, puis recopiées ici. Un exercice qui simule mal ce que fait une
    commande enseigne une chose fausse, et l'élève le découvrira dans
    son terminal.
    """

    LINUX_KEYS = ("lx_caches", "lx_parent", "lx_compter", "lx_fin_journal",
                  "lx_ranger", "lx_ajouter", "lx_chercher", "lx_colonne",
                  "lx_trier", "lx_dedoublonner", "lx_palmares",
                  "lx_chmod_octal", "lx_chmod_symbolique", "lx_trouver",
                  "lx_menage", "lx_args", "lx_enchainer", "lx_remplacer",
                  "lx_total", "lx_pour_chaque")

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({
            "TESTING": True,
            "DATABASE": self.path,
            "SECRET_KEY": "test",
            "ADMIN_USER": "prof",
            "ADMIN_PASSWORD": "secret",
        })
        self.admin = self.app.test_client()
        self.admin.post("/admin/login",
                        data={"username": "prof", "password": "secret"})

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def chapitre(self):
        for chapter in ex.CHAPTERS:
            if chapter.key == "linux":
                return chapter
        raise AssertionError("pas de chapitre Linux")

    def test_the_chapter_holds_four_modules(self):
        chapitre = self.chapitre()
        self.assertEqual([m.key for m in chapitre.modules],
                         ["linux_fichiers", "linux_filtres", "linux_droits",
                          "linux_shell"])
        for module in chapitre.modules:
            for key in module.keys:
                self.assertIn(key, ex.PATTERNS, key)

    def test_the_chapter_covers_every_difficulty(self):
        """Des exercices faciles, moyens et difficiles, pas un seul palier."""
        niveaux = {ex.PATTERNS[k].level
                   for m in self.chapitre().modules for k in m.keys}
        self.assertEqual(niveaux, set(ex.LEVELS))

    def test_the_chapter_uses_the_three_modes(self):
        modes = {ex.PATTERNS[k].mode
                 for m in self.chapitre().modules for k in m.keys}
        self.assertEqual(modes, {"complete", "debug", "predict"})

    def test_every_exercise_shows_a_session_or_a_script(self):
        """Un bloc commence par une invite, ou c'est un script à lire."""
        for module in self.chapitre().modules:
            for key in module.keys:
                with self.subTest(exercice=key):
                    tpl = ex.PATTERNS[key].tpl
                    self.assertTrue(tpl.startswith("$ ")
                                    or tpl.startswith("#!/bin/bash"), tpl[:20])

    def test_every_session_explains_how_to_read_itself(self):
        """L'élève qui ne voit qu'un exercice doit savoir lire le bloc."""
        for module in self.chapitre().modules:
            for key in module.keys:
                pattern = ex.PATTERNS[key]
                if pattern.mode != "complete":
                    continue        # diagnostic et prédiction : un script,
                                    # ou un rappel qui leur est propre
                with self.subTest(exercice=key):
                    self.assertIn("session de terminal", pattern.lesson[0])

    def test_listing_the_hidden_entries(self):
        self.assertEqual(
            ex.target_rows("lx_caches", {"g": 0, **ex.PATTERNS["lx_caches"]
                                         .derive({"g": 0})}),
            [".", "..", ".bashrc", ".config", "notes.txt", "rapport.pdf"])

    def test_counting_the_lines_of_a_file(self):
        params = dict(g=0, **ex.PATTERNS["lx_compter"].derive({"g": 0}))
        self.assertEqual(ex.target_rows("lx_compter", params),
                         ["4 courses.txt"])

    def test_moving_a_file_into_another_directory(self):
        params = dict(g=0, n=1,
                      **ex.PATTERNS["lx_ranger"].derive({"g": 0, "n": 1}))
        self.assertEqual(ex.target_rows("lx_ranger", params),
                         [".:", "agenda.txt", "sauvegarde", "",
                          "sauvegarde:", "rapport.txt"])

    def test_the_ranking_pipeline_counts_and_sorts(self):
        """sort | uniq -c | sort -rn | head : comptes alignés sur 7 colonnes."""
        params = dict(g=0, **ex.PATTERNS["lx_palmares"].derive({"g": 0}))
        self.assertEqual(ex.target_rows("lx_palmares", params),
                         ["      4 lyon", "      3 paris", "      2 nice"])

    def test_a_symbolic_chmod_only_touches_what_it_names(self):
        tirage = {"g": 0, "d": 0}
        params = dict(tirage,
                      **ex.PATTERNS["lx_chmod_symbolique"].derive(tirage))
        self.assertEqual(
            ex.target_rows("lx_chmod_symbolique", params),
            ["-rwxrw-r-- 1 ada ada 128 Sep 22 12:28 sauvegarde.sh"])

    def test_find_descends_where_a_star_does_not(self):
        params = dict(g=0, **ex.PATTERNS["lx_trouver"].derive({"g": 0}))
        self.assertEqual(ex.target_rows("lx_trouver", params),
                         ["./erreurs.log", "./src/debug.log"])

    def test_an_unquoted_variable_is_split_on_its_spaces(self):
        tirage = {"g": 0, "n": 2}
        params = dict(tirage,
                      **ex.PATTERNS["lx_bug_guillemets"].derive(tirage))
        self.assertEqual(ex.target_rows("lx_bug_guillemets", params),
                         ["2 rapport final.txt"])
        self.assertEqual(ex.broken_rows("lx_bug_guillemets", params),
                         ["wc: rapport: No such file or directory",
                          "wc: final.txt: No such file or directory",
                          "0 total"])

    def test_a_menu_never_names_a_file_the_draw_can_rename(self):
        """Une option est un texte figé : elle ne suit pas le tirage.

        Si un menu propose `sort liste.txt`, le fichier doit s'appeler
        ainsi dans **tous** les tirages — ou dans aucun, pour un fichier
        qu'on cite justement parce qu'il n'existe pas. Un nom qui change
        d'un élève à l'autre donnerait une commande qui ne parle pas du
        fichier montré.
        """
        nom_de_fichier = re.compile(r"\b[a-z0-9_]+\.[a-z]+\b")
        for key in self.LINUX_KEYS:
            pattern = ex.PATTERNS[key]
            cites = {mot
                     for _label, options in pattern.blanks.values()
                     for opt in options
                     for mot in nom_de_fichier.findall(opt.c)}
            for nom in cites:
                presences = {nom in ex.render_code(key, params,
                                                   dict(pattern.ref))
                             for params in tirages(pattern)}
                with self.subTest(exercice=key, fichier=nom):
                    self.assertEqual(len(presences), 1, nom)

    def test_a_linux_exercise_is_solved_like_any_other(self):
        resp = self.admin.post("/admin/sessions", data={
            "title": "TP Linux", "patterns": ["lx_chercher", "carre"]})
        session_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        self.admin.post("/admin/sessions/%d/open" % session_id)
        page = self.admin.get("/admin/sessions/%d" % session_id) \
                         .get_data(as_text=True)
        code = page.split('class="joincode mono">')[1].split("<")[0].strip()
        client = self.app.test_client()
        client.post("/join", data={"first_name": "Ada",
                                   "last_name": "Lovelace", "code": code})
        task = client.get("/api/task/lx_chercher").get_json()
        self.assertEqual(task["module"], "Filtrer, trier, compter")
        verdict = client.post("/api/task/lx_chercher/check",
                              json={"selection": {"cmd": "a"}}).get_json()
        self.assertTrue(verdict["ok"])

    def test_the_run_button_speaks_the_language_of_its_chapter(self):
        """On compile un programme, on exécute une commande."""
        resp = self.admin.post("/admin/sessions", data={
            "title": "TP mixte", "patterns": ["lx_chercher", "carre"]})
        session_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        self.admin.post("/admin/sessions/%d/open" % session_id)
        page = self.admin.get("/admin/sessions/%d" % session_id) \
                         .get_data(as_text=True)
        code = page.split('class="joincode mono">')[1].split("<")[0].strip()
        client = self.app.test_client()
        client.post("/join", data={"first_name": "Ada",
                                   "last_name": "Lovelace", "code": code})
        self.assertEqual(client.get("/api/task/carre").get_json()["action"],
                         "Compiler et exécuter")
        self.assertEqual(
            client.get("/api/task/lx_chercher").get_json()["action"],
            "Exécuter la commande")


class ChargeTest(unittest.TestCase):
    """Ce que chaque requête coûte à la base.

    L'hébergement monte le disque par le réseau : une écriture SQLite y
    prend un verrou exclusif et coûte cent fois ce qu'elle coûte ici.
    Avec trente copies qui sondent en boucle, le nombre de requêtes SQL
    par sondage n'est pas un détail d'implémentation, c'est un budget.
    """

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({
            "TESTING": True,
            "DATABASE": self.path,
            "SECRET_KEY": "test",
            "ADMIN_USER": "prof",
            "ADMIN_PASSWORD": "secret",
        })
        self.admin = self.app.test_client()
        self.admin.post("/admin/login",
                        data={"username": "prof", "password": "secret"})
        resp = self.admin.post("/admin/sessions", data={
            "title": "TP", "patterns": ["ligne", "lx_chercher"]})
        self.session_id = int(
            resp.headers["Location"].rstrip("/").split("/")[-1])
        self.admin.post("/admin/sessions/%d/open" % self.session_id)
        page = self.admin.get("/admin/sessions/%d" % self.session_id) \
                         .get_data(as_text=True)
        code = page.split('class="joincode mono">')[1].split("<")[0].strip()
        self.client = self.app.test_client()
        self.client.post("/join", data={"first_name": "Ada",
                                        "last_name": "Lovelace",
                                        "code": code})

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def sql(self, appel):
        """Les ordres SQL qu'une requête HTTP envoie à la base."""
        vus = []
        vrai_connect = sqlite3.connect

        def espion(*args, **kwargs):
            conn = vrai_connect(*args, **kwargs)
            conn.set_trace_callback(
                lambda ordre: vus.append(" ".join(ordre.split())))
            return conn

        sqlite3.connect = espion
        try:
            appel()
        finally:
            sqlite3.connect = vrai_connect
        return vus

    @staticmethod
    def ecritures(ordres):
        return [o for o in ordres
                if o.split(" ")[0].upper() in ("INSERT", "UPDATE", "DELETE")]

    def last_seen(self):
        with self.app.app_context():
            return db.query("SELECT last_seen_at FROM student WHERE id = 1",
                            one=True)["last_seen_at"]

    def set_last_seen(self, secondes):
        with self.app.app_context():
            db.execute("UPDATE student SET last_seen_at = ? WHERE id = 1",
                       (db.ago(secondes),))

    def test_a_recent_activity_is_not_rewritten(self):
        """Réécrire la même seconde à chaque tour ne dit rien de plus.

        L'ordre part quand même, mais il ne trouve aucune ligne : SQLite
        ne salit aucune page, ne prend pas le verrou d'écriture et n'a
        rien à confirmer sur le disque. C'est là qu'est l'économie.
        """
        self.set_last_seen(10)          # bien en deçà de SEEN_INTERVAL
        avant = self.last_seen()
        self.client.post("/api/heartbeat")
        self.assertEqual(self.last_seen(), avant)

    def test_an_old_activity_is_written_again(self):
        self.set_last_seen(student.SEEN_INTERVAL + 60)
        avant = self.last_seen()
        self.client.post("/api/heartbeat")
        self.assertGreater(self.last_seen(), avant)

    def test_the_heartbeat_says_when_the_session_is_over(self):
        """Un seul sondage sur la page : il doit porter la clôture aussi."""
        vivant = self.client.post("/api/heartbeat").get_json()
        self.assertEqual(vivant["session_status"], "open")
        self.admin.post("/admin/sessions/%d/close" % self.session_id)
        fini = self.client.post("/api/heartbeat").get_json()
        self.assertEqual(fini["session_status"], "closed")

    def test_the_progress_reads_the_tasks_only_once(self):
        lectures = [o for o in self.sql(lambda: self.client.get("/api/me"))
                    if "FROM task WHERE student_id" in o]
        self.assertEqual(len(lectures), 1, lectures)

    def test_the_student_flood_does_not_recheck_the_catalogue(self):
        """L'empreinte du catalogue ne bouge pas pendant une épreuve."""
        self.client.post("/api/heartbeat")
        ordres = self.sql(lambda: self.client.post("/api/heartbeat"))
        self.assertEqual([o for o in ordres if "FROM qcm_module" in o], [])

    def test_the_teacher_pages_still_see_an_import_at_once(self):
        """Ce que l'espacement ne doit pas coûter : l'import reste immédiat."""
        self.admin.get("/admin/")
        ordres = self.sql(lambda: self.admin.get("/admin/"))
        self.assertTrue([o for o in ordres if "FROM qcm_module" in o], ordres)

    def test_the_budget_of_a_polling_round(self):
        """Le budget complet d'un tour de sondage, verrouillé par un chiffre.

        Cinq ordres : identifier la copie, et lire ses tâches, autour
        d'un UPDATE conditionnel qui ne touche aucune ligne tant que
        l'activité est fraîche. Trente copies sondent toutes les trente
        secondes : ce nombre est multiplié par soixante chaque minute.
        """
        self.set_last_seen(10)
        ordres = [o for o in self.sql(lambda: self.client.post("/api/heartbeat"))
                  if not o.startswith("PRAGMA")]
        self.assertEqual(len(ordres), 5, ordres)
        self.assertEqual(len([o for o in ordres if "FROM task" in o]), 1)
        self.assertEqual([o for o in ordres if "FROM qcm_module" in o], [])

class CatalogueTest(unittest.TestCase):
    """Le catalogue doit rester cohérent quand on ajoute des modules."""

    def test_every_exercise_belongs_to_exactly_one_module(self):
        vus = []
        for module in ex.MODULES:
            vus.extend(module.keys)
        self.assertEqual(sorted(vus), sorted(ex.ALL_KEYS))
        self.assertEqual(len(vus), len(set(vus)), "exercice dans deux modules")

    def test_module_keys_all_exist(self):
        for module in ex.MODULES:
            for key in module.keys:
                self.assertIn(key, ex.PATTERNS, "%s/%s" % (module.key, key))

    def test_every_exercise_can_be_brought_to_zero(self):
        """Épuiser les réponses d'un exercice doit toujours l'annuler."""
        for key in ex.ALL_KEYS:
            with self.subTest(exercice=key):
                choices = ex.answer_space(key)
                self.assertGreaterEqual(choices, 2, key)
                self.assertEqual(scoring.kept_share(choices, choices - 1), 0.0)
                self.assertGreater(scoring.kept_share(choices, choices - 2), 0.0)

    def test_the_answer_space_counts_the_menu_combinations(self):
        """Deux menus de quatre options font seize réponses, pas huit."""
        self.assertEqual(ex.answer_space("carre"), 4)
        self.assertEqual(ex.answer_space("triangle_droite"), 16)
        # La prédiction n'a pas de menu : elle reçoit l'allocation par défaut.
        for key in ex.ALL_KEYS:
            if ex.PATTERNS[key].mode == "predict":
                with self.subTest(exercice=key):
                    self.assertEqual(ex.answer_space(key), ex.PREDICT_CHOICES)

    def test_every_module_is_described(self):
        for module in ex.MODULES:
            self.assertTrue(module.title.strip(), module.key)
            self.assertTrue(module.summary.strip(), module.key)
            self.assertIn(module.level, ex.LEVELS, module.key)

    def test_catalogue_covers_every_exercise(self):
        vus = [p.key
               for _chapitre, modules in ex.catalogue()
               for _module, niveaux in modules
               for _lvl, _nom, motifs in niveaux
               for p in motifs]
        self.assertEqual(sorted(vus), sorted(ex.ALL_KEYS))

    def test_every_module_belongs_to_a_chapter(self):
        dans_chapitres = [m.key for c in ex.CHAPTERS for m in c.modules]
        self.assertEqual(sorted(dans_chapitres),
                         sorted(m.key for m in ex.MODULES))
        for key in ex.ALL_KEYS:
            self.assertIsNotNone(ex.chapter_of(key), key)


class TraceConsistencyTest(unittest.TestCase):
    """La trace doit raconter exactement ce que produit la sortie."""

    def test_last_step_matches_the_produced_output(self):
        for key, pattern in ex.PATTERNS.items():
            if pattern.trace is None:
                continue
            blank_id = list(pattern.blanks)[0]
            for params in tirages(pattern):
                for option in pattern.blanks[blank_id][1]:
                    selection = {blank_id: option.id}
                    with self.subTest(pattern=key, params=params,
                                      choix=option.c):
                        steps = ex.build_trace(key, params, selection)
                        try:
                            rows = ex.build_rows(key, params, selection)
                        except ex.InfiniteLoop:
                            self.assertTrue(steps[-1]["infinite"])
                            continue
                        self.assertFalse(steps[-1].get("infinite", False))
                        self.assertEqual(steps[-1]["sortie"], rows[0].rstrip())

    def test_every_level_is_named(self):
        for pattern in ex.PATTERNS.values():
            self.assertIn(pattern.level, ex.LEVELS, pattern.key)


class SubstituteTest(unittest.TestCase):

    def test_variables_are_replaced_by_their_values(self):
        self.assertEqual(ex.substitute("j < n", {"j": 2, "n": 5}), "2 < 5")
        self.assertEqual(ex.substitute("j < n - 1", {"j": 4, "n": 5}), "4 < 5 - 1")

    def test_unknown_names_are_left_alone(self):
        self.assertEqual(ex.substitute("j <= h", {"j": 1}), "1 <= h")


class PatternTest(unittest.TestCase):
    """La cible doit differer des mauvais choix, sinon l'exercice est vain."""

    def test_reference_output_is_unique_per_blank(self):
        for key, pattern in ex.PATTERNS.items():
            if pattern.mode != "complete":
                continue    # prediction : aucun menu ; diagnostic : pas de
                            # sortie a comparer, la reponse est une cause
            for params in tirages(pattern):
                target = ex.target_rows(key, params)
                for blank_id, (_label, options) in pattern.blanks.items():
                    for opt in options:
                        if opt.id == pattern.ref[blank_id]:
                            continue
                        selection = dict(pattern.ref)
                        selection[blank_id] = opt.id
                        try:
                            produced = ex.build_rows(key, params, selection)
                        except ex.InfiniteLoop:
                            continue    # ne peut pas coincider avec la cible
                        except (ValueError, ZeroDivisionError):
                            continue
                        ok, _ = ex.compare(produced, target)
                        self.assertFalse(
                            ok,
                            "%s/%s : l'option %r produit la meme sortie que la "
                            "reference pour %s" % (key, blank_id, opt.c, params))


if __name__ == "__main__":
    unittest.main(verbosity=2)
