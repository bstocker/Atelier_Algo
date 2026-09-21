"""Chapitre QCM : import de questionnaires au format Excel.

Un module de QCM importé vit dans la base, pas dans le code : l'enseignant
dépose un classeur depuis la console, et le sous-module apparaît aussitôt
dans le catalogue, à côté de « Docker : les bases » livré avec
l'application. Les deux produisent le même objet — un `Module` et des
`Pattern` en mode `qcm` — si bien que la composition d'une session, la
correction, le barème et la surveillance s'appliquent sans rien changer.

Le format du classeur est décrit dans le README, et le modèle
téléchargeable depuis la console est produit par `model_workbook()` : les
deux ne peuvent pas diverger, puisque le modèle est relu par le même
analyseur que les fichiers de l'enseignant.

Plusieurs processus servent l'application : un import fait dans l'un doit
être vu par les autres. `sync()` compare donc une empreinte de la base au
catalogue chargé, et ne rebâtit que lorsqu'elle a changé.
"""

import io
import json
import re
import threading
import unicodedata

from . import exercises
from .db import execute, get_db, now, query
from .engine import CHOICE_LETTERS, QCM_CHOICES, Module, qcm_pattern

CHAPTER_KEY = "qcm"

# Colonnes attendues : en-tete reconnu -> champ. La reconnaissance est faite
# sans accent ni casse, pour qu'un « Bonne reponse » tape a la volee passe
# aussi bien qu'un « Bonne réponse ».
COLUMNS = {
    "question": "question",
    "reponse a": "a", "reponse b": "b", "reponse c": "c", "reponse d": "d",
    "bonne reponse": "answer",
    "explication": "explanation",
    "niveau": "level",
}
REQUIRED = ("question", "a", "b", "c", "d", "answer")

MAX_QUESTION = 500
MAX_CHOICE = 300
MAX_EXPLANATION = 800


class BadWorkbook(Exception):
    """Classeur refusé.

    Le message est montré tel quel à l'enseignant : il doit dire quelle
    ligne pose problème et ce qui était attendu, pas « import échoué ».
    """


def _plain(text):
    """Minuscules, sans accent ni espace superflu — pour comparer des titres."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def _cell(value):
    return " ".join(str(value).split()) if value is not None else ""


def slugify(title):
    """Cle de module tiree du titre : « Docker & Cie » -> « docker-cie »."""
    slug = re.sub(r"[^a-z0-9]+", "-", _plain(title)).strip("-")
    return slug or "qcm"


# --------------------------------------------------------------------------
# Lecture d'un classeur
# --------------------------------------------------------------------------

# Le deploiement televerse des fichiers, il n'installe pas de paquet :
# openpyxl doit etre pose a la main, une fois, dans une console de
# l'hebergeur. Le message le dit avec la commande exacte, et l'application
# demarre sans lui — seul l'import de QCM est indisponible.
NO_OPENPYXL = (
    "La lecture des classeurs Excel demande la bibliothèque openpyxl, "
    "absente de cet hébergement. Ouvrez une console Bash et tapez : "
    "pip install --user openpyxl"
)


def _load_workbook(stream):
    try:
        from openpyxl import load_workbook
    except ImportError:                                   # pragma: no cover
        raise BadWorkbook(NO_OPENPYXL)
    try:
        return load_workbook(stream, read_only=True, data_only=True)
    except Exception:
        raise BadWorkbook(
            "Fichier illisible. Attendu : un classeur Excel (.xlsx) ; "
            "un .xls ou un .csv doit d'abord être enregistré au format .xlsx.")


def _header_map(row):
    """Associe chaque champ attendu a son indice de colonne."""
    found = {}
    for index, cell in enumerate(row):
        field = COLUMNS.get(_plain(cell))
        if field and field not in found:
            found[field] = index
    missing = [name for name, field in
               (("Question", "question"), ("Réponse A", "a"),
                ("Réponse B", "b"), ("Réponse C", "c"), ("Réponse D", "d"),
                ("Bonne réponse", "answer"))
               if field not in found]
    if missing:
        raise BadWorkbook(
            "Colonnes manquantes en première ligne : %s. "
            "Téléchargez le modèle pour retrouver les intitulés attendus."
            % ", ".join(missing))
    return found


def _answer_index(raw, line):
    """Lit « B », « b », « 2 » ou le texte d'une proposition -> 0..3."""
    value = _plain(raw)
    if not value:
        raise BadWorkbook("Ligne %d : la bonne réponse est vide." % line)
    letter = value.upper()
    if len(letter) == 1 and letter in CHOICE_LETTERS:
        return CHOICE_LETTERS.index(letter)
    if value.isdigit() and 1 <= int(value) <= QCM_CHOICES:
        return int(value) - 1
    raise BadWorkbook(
        "Ligne %d : bonne réponse « %s » incomprise. Attendu : A, B, C ou D."
        % (line, _cell(raw)))


def _level(raw, line):
    value = _cell(raw)
    if not value:
        return 2
    try:
        level = int(float(value))
    except ValueError:
        raise BadWorkbook("Ligne %d : niveau « %s » incompris. Attendu : "
                           "un entier de 1 à 4." % (line, value))
    if not 1 <= level <= 4:
        raise BadWorkbook("Ligne %d : niveau %d hors de l'échelle 1 à 4."
                           % (line, level))
    return level


def parse(stream):
    """Rend la liste des questions d'un classeur, ou lève `BadWorkbook`.

    La premiere feuille seule est lue. Les lignes entierement vides sont
    ignorees : un classeur se termine souvent par des lignes fantomes.
    """
    workbook = _load_workbook(stream)
    try:
        sheet = workbook.worksheets[0]
        rows = sheet.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            raise BadWorkbook("Le classeur est vide.")
        columns = _header_map(header)

        questions = []
        for number, row in enumerate(rows, start=2):
            if not any(_cell(cell) for cell in row):
                continue
            questions.append(_read_row(row, columns, number))
    finally:
        workbook.close()

    if not questions:
        raise BadWorkbook(
            "Aucune question trouvée. La première ligne porte les intitulés, "
            "les suivantes les questions.")
    return questions


def _read_row(row, columns, line):
    def value(field):
        index = columns.get(field)
        return _cell(row[index]) if index is not None and index < len(row) else ""

    question = value("question")
    if not question:
        raise BadWorkbook("Ligne %d : la question est vide." % line)

    choices = [value(field) for field in ("a", "b", "c", "d")]
    empty = [CHOICE_LETTERS[i] for i, text in enumerate(choices) if not text]
    if empty:
        raise BadWorkbook(
            "Ligne %d : proposition %s vide. Les quatre réponses sont "
            "obligatoires." % (line, ", ".join(empty)))
    if len({_plain(c) for c in choices}) < QCM_CHOICES:
        raise BadWorkbook(
            "Ligne %d : deux propositions sont identiques." % line)

    return {
        "question": question[:MAX_QUESTION],
        "choices": [c[:MAX_CHOICE] for c in choices],
        "answer": _answer_index(value("answer"), line),
        "level": _level(value("level"), line),
        "explanation": value("explanation")[:MAX_EXPLANATION],
    }


# --------------------------------------------------------------------------
# Enregistrement
# --------------------------------------------------------------------------

def _free_key(title):
    """Cle de module libre, suffixee au besoin : docker, docker-2, docker-3."""
    base = slugify(title)
    taken = {row["key"] for row in query("SELECT key FROM qcm_module")}
    if base not in taken:
        return base
    for suffix in range(2, 100):
        candidate = "%s-%d" % (base, suffix)
        if candidate not in taken:
            return candidate
    raise BadWorkbook("Trop de modules portent déjà ce titre.")


def save(title, summary, questions, source=""):
    """Enregistre un module importe et rend sa cle."""
    title = " ".join(str(title or "").split())[:120] or "QCM sans titre"
    key = _free_key(title)
    # Le niveau du module resume celui de ses questions : c'est un reperage
    # pour l'enseignant qui compose, pas une note.
    level = round(sum(q["level"] for q in questions) / len(questions))

    module_id = execute(
        """INSERT INTO qcm_module (key, title, summary, level, source,
                                   imported_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (key, title, " ".join(str(summary or "").split())[:300],
         level, str(source or "")[:120], now()),
    )
    db = get_db()
    for position, item in enumerate(questions, start=1):
        db.execute(
            """INSERT INTO qcm_question (module_id, key, position, question,
                                         choices, answer, level, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (module_id, "qcm_%s_%03d" % (key.replace("-", "_"), position),
             position, item["question"], json.dumps(item["choices"]),
             item["answer"], item["level"], item["explanation"]),
        )
    db.commit()
    return key


def delete(key):
    """Supprime un module importe. Rend False s'il est inconnu."""
    module = query("SELECT * FROM qcm_module WHERE key = ?", (key,), one=True)
    if module is None:
        return False
    execute("DELETE FROM qcm_module WHERE id = ?", (module["id"],))
    return True


def used_by(key):
    """Intitules des sessions qui utilisent ce module.

    Un module supprime emporterait ses questions, et les copies qui les
    citent n'auraient plus de quoi s'afficher : on refuse plutot.
    """
    keys = {row["key"] for row in query(
        """SELECT q.key FROM qcm_question q JOIN qcm_module m
                  ON m.id = q.module_id
            WHERE m.key = ?""", (key,))}
    if not keys:
        return []
    return [room["title"] for room in query("SELECT title, patterns FROM session")
            if keys & set(json.loads(room["patterns"]))]


# --------------------------------------------------------------------------
# Chargement du catalogue
# --------------------------------------------------------------------------

def imported():
    """Modules importes, avec leurs questions, dans l'ordre d'import."""
    rows = query("SELECT * FROM qcm_module ORDER BY imported_at, id")
    if not rows:
        return []
    by_module = {}
    for question in query("SELECT * FROM qcm_question ORDER BY module_id, position"):
        by_module.setdefault(question["module_id"], []).append(question)
    return [(row, by_module.get(row["id"], [])) for row in rows]


def build(module_row, questions):
    """Fabrique le `Module` et les `Pattern` d'un module importe."""
    patterns = [
        qcm_pattern(q["key"], q["position"], q["question"],
                    json.loads(q["choices"]), q["answer"], q["level"],
                    q["explanation"])
        for q in questions
    ]
    module = Module(
        key=module_row["key"],
        title=module_row["title"],
        level=module_row["level"],
        summary=module_row["summary"],
        keys=tuple(p.key for p in patterns),
    )
    return module, patterns


def signature():
    """Empreinte bon marche de la base : change des qu'un import a lieu.

    Le dernier identifiant compte autant que les effectifs : supprimer un
    module puis en importer un autre laisserait sinon l'empreinte intacte.
    """
    row = query(
        """SELECT (SELECT COUNT(*) FROM qcm_module)      AS modules,
                  (SELECT COUNT(*) FROM qcm_question)    AS questions,
                  (SELECT COALESCE(MAX(id), 0) FROM qcm_module) AS last""",
        one=True,
    )
    return (row["modules"], row["questions"], row["last"])


# --------------------------------------------------------------------------
# Le modele a telecharger
# --------------------------------------------------------------------------

HEADER_ROW = ("Question", "Réponse A", "Réponse B", "Réponse C", "Réponse D",
              "Bonne réponse", "Explication", "Niveau")


def model_workbook(patterns):
    """Rend un classeur modele, rempli avec un QCM existant.

    Le modele n'est pas ecrit a la main : il est produit a partir du module
    livre avec l'application, puis relu par le meme analyseur que les
    fichiers de l'enseignant. Le format documente et le format accepte ne
    peuvent donc pas diverger — un test verifie l'aller-retour.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError:                                   # pragma: no cover
        raise BadWorkbook(NO_OPENPYXL)

    book = Workbook()
    sheet = book.active
    sheet.title = "QCM"
    sheet.append(HEADER_ROW)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for pattern in patterns:
        label, options = pattern.blanks["choix"]
        answer = [o.id for o in options].index(pattern.ref["choix"])
        # L'explication est rangee dans le retour de chaque proposition,
        # prefixe du verdict : on la reprend telle qu'elle a ete ecrite.
        note = options[answer].note
        explanation = note[len("Exact."):].strip() if note.startswith("Exact.") \
            else note
        sheet.append((label, options[0].c, options[1].c, options[2].c,
                      options[3].c, CHOICE_LETTERS[answer], explanation,
                      pattern.level))

    widths = (60, 34, 34, 34, 34, 14, 60, 8)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
    for row in sheet.iter_rows(min_row=1):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


_loaded = None          # empreinte du catalogue actuellement charge
_lock = threading.Lock()


def sync(force=False):
    """Recharge les modules importes si la base a bouge.

    Appelee a chaque requete : plusieurs processus servent l'application,
    et un import fait dans l'un doit etre vu par les autres. Le cas courant
    ne coute qu'une requete et une comparaison de triplet.

    Le verrou protege la fenetre pendant laquelle les anciens motifs sont
    sortis du registre et les nouveaux pas encore entres.
    """
    global _loaded
    stamp = signature()
    if stamp == _loaded and not force:
        return
    with _lock:
        if stamp == _loaded and not force:
            return
        exercises.refresh([build(row, questions)
                           for row, questions in imported()])
        _loaded = stamp
