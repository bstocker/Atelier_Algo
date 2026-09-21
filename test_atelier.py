"""Tests de bout en bout : session, exercices, penalites, notation."""

import itertools
import json
import os
import shutil
import tempfile
import unittest

from markupsafe import escape

from atelier import create_app, db, load_env_file, exercises as ex, scoring


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
        """Le schéma courant, privé de la colonne ajoutée après coup."""
        import sqlite3
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "atelier", "schema.sql"),
                  encoding="utf-8") as fh:
            schema = fh.read()
        for table, column, _decl in db.ADDED_COLUMNS:
            schema = "\n".join(line for line in schema.splitlines()
                               if not line.strip().startswith(column))
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

    def _columns(self):
        import sqlite3
        conn = sqlite3.connect(self.path)
        try:
            return [row[1] for row in conn.execute("PRAGMA table_info(task)")]
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

    def test_the_cost_is_proportional_to_the_value_of_an_exercise(self):
        """Le même exercice coûte moins cher dans une session plus longue."""
        self.assertEqual(scoring.attempt_cost(4, 4), 5.0 / 3)
        self.assertEqual(scoring.attempt_cost(8, 4), 2.5 / 3)
        self.assertEqual(scoring.exercise_value(8), 2.5)
        self.assertEqual(scoring.exercise_value(0), 0.0)


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
