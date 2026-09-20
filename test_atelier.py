"""Tests de bout en bout : session, exercices, penalites, notation."""

import json
import os
import shutil
import tempfile
import unittest

from atelier import create_app, load_env_file, exercises as ex, scoring


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
        task = client.get("/api/task/" + key).get_json()
        ref = dict(ex.PATTERNS[key].ref)
        return client.post("/api/task/%s/check" % key,
                           json={"selection": ref}).get_json()

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

    def test_unknown_pattern_is_404(self):
        _, code = self.make_session(patterns=("carre",))
        client, _ = self.join(code)
        self.assertEqual(client.get("/api/task/losange").status_code, 404)
        self.assertEqual(client.post("/api/task/carre_magique/check",
                                     json={"selection": {}}).status_code, 404)


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
        self.assertEqual(scoring.final_score(8, 8, 0), 20.0)
        self.assertEqual(scoring.final_score(0, 8, 0), 0.0)
        self.assertEqual(scoring.final_score(4, 8, 20), 0.0)
        self.assertEqual(scoring.final_score(0, 0, 0), 0.0)


class PatternTest(unittest.TestCase):
    """La cible doit differer des mauvais choix, sinon l'exercice est vain."""

    def test_reference_output_is_unique_per_blank(self):
        for key, pattern in ex.PATTERNS.items():
            name, lo, hi = pattern.dim or pattern.value
            for size in range(lo, hi + 1):
                params = {name: size}
                target = ex.target_rows(key, params)
                for blank_id, (_label, options) in pattern.blanks.items():
                    for opt in options:
                        if opt.id == pattern.ref[blank_id]:
                            continue
                        selection = dict(pattern.ref)
                        selection[blank_id] = opt.id
                        try:
                            produced = ex.build_rows(key, params, selection)
                        except (ValueError, ZeroDivisionError):
                            continue
                        ok, _ = ex.compare(produced, target)
                        self.assertFalse(
                            ok,
                            "%s/%s : l'option %r produit la meme sortie que la "
                            "reference pour %s" % (key, blank_id, opt.c, params))


if __name__ == "__main__":
    unittest.main(verbosity=2)
