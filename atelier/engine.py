"""Socle du moteur d'exercices : structures, fabriques et correction.

Chaque exercice est une donnee : un gabarit de code C troue, des menus
d'options, et une fonction qui reconstruit la sortie ligne a ligne. Le
rendu de la cible et la correction utilisent le meme code, si bien qu'une
selection est juste exactement quand elle reproduit la cible.

Tout est evalue cote serveur : le navigateur ne recoit jamais la reponse
attendue, seulement le resultat a obtenir.

Aucun exercice ici : ils vivent dans atelier/modules/, et
atelier/exercises.py assemble le catalogue.
"""

from dataclasses import dataclass
from typing import Callable
import random
import re

BLANK_PLACEHOLDER = "__________"

# Niveaux de difficulte, affiches a l'enseignant quand il compose sa session.
LEVELS = {
    1: "Découverte",
    2: "Facile",
    3: "Moyen",
    4: "Avancé",
}


@dataclass(frozen=True)
class Chapter:
    """Un chapeau au-dessus des modules : un langage, un domaine.

    « Langage C » réunit les boucles, les conditions, les tableaux… Un
    futur chapitre pourrait réunir des modules d'un autre langage.

    `action` est le libellé du bouton qui lance la vérification. On ne
    compile pas une ligne de commande : chaque chapitre nomme le geste
    dans ses propres termes.
    """
    key: str
    title: str
    summary: str
    modules: tuple
    action: str = "Compiler et exécuter"


@dataclass(frozen=True)
class Module:
    """Un ensemble d'exercices sur un meme sujet.

    Les modules structurent le catalogue : « Les boucles » aujourd'hui,
    « Les conditions » ou un module de quiz demain. Chacun porte son titre
    et son niveau ; les exercices gardent le leur, plus fin, a l'interieur.
    """
    key: str
    title: str
    level: int
    summary: str
    keys: tuple


class InfiniteLoop(Exception):
    """La selection de l'eleve produit une boucle qui ne s'arrete jamais."""


def _never_ends(_ctx):
    raise InfiniteLoop()


@dataclass(frozen=True)
class Option:
    id: str
    c: str                  # texte affiche, et injecte dans le code si trou
    fn: Callable = None     # semantique : nombre d'iterations, predicat, valeur
    note: str = ""          # retour affiche apres coup, en mode diagnostic


@dataclass(frozen=True)
class Pattern:
    key: str
    name: str
    brief: str
    why: str
    tpl: str                              # gabarit avec des marqueurs @blank@
    blanks: dict                          # blank_id -> (label, [Option])
    ref: dict                             # blank_id -> option_id de reference
    rows: Callable                        # (params, get) -> list[str]
    dim: tuple = None                     # (nom, mini, maxi) tire au hasard
    value: tuple = None                   # (nom, mini, maxi) saisi au clavier
    dims: tuple = ()                      # plusieurs tirages : ((nom, a, b), …)
    derive: Callable = None               # params tires -> params supplementaires
    trace: Callable = None                # (params, get, text) -> list[dict]
    lesson: tuple = ()                    # points a retenir, affiches en tete
    level: int = 2                        # cle de LEVELS
    teacher_note: str = ""                # visible du seul enseignant
    mode: str = "complete"                # complete | predict | debug
    broken: Callable = None               # mode debug : la sortie erronee


def _opts(*triples):
    return [Option(oid, c, fn) for oid, c, fn in triples]


def _diag(*triples):
    """Diagnostics d'un exercice « trouver le bug » : texte + explication."""
    return [Option(oid, texte, None, note) for oid, texte, note in triples]


_VARS = re.compile(r"\b([a-zA-Z]+)\b")


def substitute(expression, values):
    """Remplace les variables d'une expression C par leurs valeurs.

    `j < n` avec j = 2 et n = 5 devient `2 < 5`. Sert a la trace : l'eleve
    voit le test tel qu'il est evalue a chaque tour, pas sa forme abstraite.
    """
    return _VARS.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(1),
        expression,
    )


# --------------------------------------------------------------------------
# Trace des boucles simples
# --------------------------------------------------------------------------

TRACE_CAP = 40          # garde-fou d'affichage
INFINITE_PREVIEW = 6    # tours montres avant de conclure a une boucle infinie


def _unroll(condition, tours, infinite, first, advance, emit, action, n):
    """Deroule une boucle a un compteur et rend les lignes de la trace.

    `condition` est deja sous forme de texte C ; les valeurs y sont
    substituees a chaque tour pour que l'eleve voie le test tel qu'il est
    evalue, et non sa forme abstraite.
    """
    steps, sortie, j = [], "", first
    for tour in range(min(tours, TRACE_CAP)):
        sortie += emit(j)
        steps.append({
            "tour": tour + 1,
            "j": j,
            "test": substitute(condition, {"j": j, "n": n}),
            "vrai": True,
            "action": action,
            "sortie": sortie.rstrip(),
        })
        j = advance(j)

    steps.append({
        "tour": None,
        "j": j,
        "test": substitute(condition, {"j": j, "n": n}),
        "vrai": infinite,
        "action": ("le test reste vrai : la boucle ne s'arrête jamais"
                   if infinite else "le test est faux : on sort de la boucle"),
        "sortie": sortie.rstrip(),
        "infinite": infinite,
    })
    return steps


def condition_trace(blank_id, first, delta, step_label):
    """Trace des boucles dont le trou est la condition, le pas etant fixe."""
    def trace(params, get, text):
        n = params["n"]
        return _unroll(
            condition=text(blank_id),
            tours=get(blank_id)({"n": n}),
            infinite=False,
            first=first(n),
            advance=lambda j: j + delta,
            emit=lambda _j: "*",
            action='printf("*")  puis  %s' % step_label,
            n=n,
        )
    return trace


def step_trace(blank_id, condition, deltas, emit, action):
    """Trace des boucles dont le trou est le pas, la condition etant fixe.

    `deltas` associe le texte C de chaque option a son deplacement. Le nombre
    de tours se deduit du deplacement, et non de la fonction du menu : selon
    les motifs celle-ci rend tantot un pas, tantot un compte. Un deplacement
    nul ou negatif n'approche jamais la sortie : la boucle est infinie.
    """
    def trace(params, get, text):
        n = params["n"]
        choix = text(blank_id)
        delta = deltas[choix](n)
        infinite = delta <= 0
        tours = INFINITE_PREVIEW if infinite else -(-n // delta)
        return _unroll(
            condition=condition,
            tours=tours,
            infinite=infinite,
            first=0,
            advance=lambda j: j + delta,
            emit=emit,
            action="%s  puis  %s" % (action, choix),
            n=n,
        )
    return trace



# --------------------------------------------------------------------------
# Mode « trouver le bug »
# --------------------------------------------------------------------------

def debug_pattern(key, name, but, defaut, tpl, attendu, obtenu,
                  diagnostics, bonne, level, dim=None, dims=(), derive=None):
    """Exercice de diagnostic : un code fautif, sa sortie, et quatre causes.

    Rien n'est cache ici — l'eleve voit ce qui etait attendu et ce qui sort.
    La difficulte est d'expliquer l'ecart, pas de le constater.

    Le nom et l'intitule designent le BUT du programme, jamais son defaut :
    un titre comme « la borne exclue » donnerait la reponse avant lecture.
    Le nom du defaut part dans `teacher_note`, que seul le formulaire de
    composition affiche.
    """
    return Pattern(
        key=key,
        name=name,
        brief="Ce programme devait %s. Il n'y arrive pas : trouvez pourquoi."
              % but,
        why="Une seule instruction est en cause.",
        teacher_note="Défaut : %s" % defaut,
        lesson=(
            "Comparez les deux sorties **ligne à ligne** : l'écart vous dit "
            "où regarder.",
            "Une seule des quatre causes proposées explique l'écart observé.",
        ),
        tpl=tpl,
        blanks={"cause": ("Quelle est la cause de l'écart ?",
                          _diag(*diagnostics))},
        ref={"cause": bonne},
        rows=lambda params, _get: attendu(params),
        broken=obtenu,
        dim=dim,
        dims=dims,
        derive=derive,
        level=level,
        mode="debug",
    )


# --------------------------------------------------------------------------
# Mode « predire la sortie »
# --------------------------------------------------------------------------

def predict_from(base, key, name, why, level, dim=None, dims=None):
    """Derive un exercice de prediction a partir d'un motif existant.

    Le code est livre complet, trous deja remplis par la selection de
    reference ; l'eleve n'a rien a choisir, il ecrit la sortie attendue.
    C'est le mode le plus resistant a une IA : il n'y a pas d'enonce a
    copier, seulement un code a lire.
    """
    tpl = base.tpl
    for blank_id, (_label, options) in base.blanks.items():
        for option in options:
            if option.id == base.ref[blank_id]:
                tpl = tpl.replace("@%s@" % blank_id, option.c)

    def reference(blank_id):
        for option in base.blanks[blank_id][1]:
            if option.id == base.ref[blank_id]:
                return option.fn
        raise KeyError(blank_id)

    return Pattern(
        key=key,
        name=name,
        brief="Lisez le code, puis écrivez la sortie qu'il produit.",
        why=why,
        lesson=(
            "Ne devinez pas : **déroulez** la boucle tour par tour, "
            "comme dans les exercices d'entrée.",
            "Les espaces comptent. Une ligne décalée d'un espace est fausse.",
            "Les espaces en fin de ligne, eux, sont ignorés.",
        ),
        tpl=tpl,
        blanks={},
        ref={},
        rows=lambda params, _get: base.rows(params, reference),
        dim=dim or base.dim,
        # Un exercice à valeur saisie garde sa valeur : sans cela, la
        # prédiction n'aurait plus aucun paramètre à tirer.
        value=base.value if dim is None else None,
        dims=dims if dims is not None else base.dims,
        derive=base.derive,
        level=level,
        mode="predict",
    )


# --------------------------------------------------------------------------
# Mode « question a choix unique »
# --------------------------------------------------------------------------

QCM_CHOICES = 4          # quatre propositions, ni plus ni moins
CHOICE_LETTERS = "ABCD"


def qcm_pattern(key, number, question, choices, answer, level=2,
                explanation=""):
    """Une question a choix unique : quatre propositions, une seule juste.

    Meme forme qu'un exercice de diagnostic — un menu, des phrases, un
    retour apres coup — si bien que la correction, le bareme et la
    surveillance s'appliquent sans rien changer.

    Le nom reste court (« Q3 ») : il sert d'etiquette dans la navigation de
    l'eleve et dans les colonnes du suivi direct, ou l'enonce entier ne
    tiendrait pas. L'enonce, lui, est l'intitule.
    """
    if len(choices) != QCM_CHOICES:
        raise ValueError("une question attend %d propositions, pas %d"
                         % (QCM_CHOICES, len(choices)))
    if not 0 <= answer < QCM_CHOICES:
        raise ValueError("la bonne réponse doit être l'une des %d propositions"
                         % QCM_CHOICES)

    # L'explication n'accompagne que la bonne reponse. La livrer sur un
    # choix faux reviendrait a donner la reponse : l'eleve n'aurait plus
    # qu'a la recocher, et le bareme perdrait tout son sens. Celui qui
    # epuise les quatre propositions finit de toute facon par la lire.
    #
    # Nommer la lettre serait faux, d'ailleurs : chaque copie recoit les
    # propositions dans son propre ordre (cf. `shuffled_blanks`).
    def note(index):
        if index != answer:
            return ""
        return "Exact. %s" % explanation if explanation else "Exact."

    return Pattern(
        key=key,
        name="Q%d" % number,
        brief=question,
        why="",
        tpl="",
        blanks={"choix": (question,
                          [Option("c%d" % i, text, None, note(i))
                           for i, text in enumerate(choices)])},
        ref={"choix": "c%d" % answer},
        rows=lambda _params, _get: [],
        level=level,
        mode="qcm",
    )


# --------------------------------------------------------------------------
# Registre
# --------------------------------------------------------------------------

# Rempli par atelier/exercises.py au chargement du catalogue. Les fonctions
# ci-dessous travaillent par cle : il leur faut un point d'entree unique.
PATTERNS = {}


def register(patterns):
    """Ajoute des exercices au registre. Refuse les cles en double."""
    for pattern in patterns:
        if pattern.key in PATTERNS:
            raise ValueError("clé d'exercice en double : %s" % pattern.key)
        PATTERNS[pattern.key] = pattern


def unregister(keys):
    """Retire des exercices du registre.

    Sert au chapitre QCM : ses modules viennent de la base, et sont
    rebatis a chaque import ou suppression.
    """
    for key in keys:
        PATTERNS.pop(key, None)


# Un exercice de prediction n'a pas de reponses enumerables : l'eleve ecrit
# un texte libre, il n'y a pas de menu a epuiser. Le bareme lui applique
# l'allocation d'un menu a quatre options, la forme la plus courante du
# catalogue, pour que l'acharnement y coute comme ailleurs.
PREDICT_CHOICES = 4


def answer_space(key):
    """Nombre de reponses distinctes que l'exercice accepte.

    Sert au bareme : un exercice a `answer_space - 1` reponses fausses, et
    les avoir toutes essayees doit ramener sa valeur a zero.
    """
    pattern = PATTERNS[key]
    if not pattern.blanks:
        return PREDICT_CHOICES
    space = 1
    for _label, options in pattern.blanks.values():
        space *= len(options)
    return space


def specs(pattern):
    """Tirages a effectuer pour cet exercice, sous forme homogene.

    Une question de QCM n'a rien a tirer : son enonce est le meme pour
    toute la classe, seul l'ordre des propositions change.
    """
    if pattern.dims:
        return pattern.dims
    spec = pattern.dim or pattern.value
    return (spec,) if spec else ()

def draw_params(key, rng=None):
    """Tire les paramètres d'un exercice.

    Un exercice peut en tirer plusieurs (`dims`) et en déduire d'autres
    (`derive`) — une phrase choisie dans une liste, les valeurs d'un
    tableau, la ligne de commande d'un programme.
    """
    rng = rng or random
    pattern = PATTERNS[key]
    params = {nom: rng.randint(lo, hi) for nom, lo, hi in specs(pattern)}
    if pattern.derive:
        params.update(pattern.derive(params))
    return params


def _getter(pattern, selection):
    """Rend une fonction blank_id -> fn, en retombant sur la reference."""
    def get(blank_id):
        options = pattern.blanks[blank_id][1]
        chosen = selection.get(blank_id)
        for opt in options:
            if opt.id == chosen:
                return opt.fn
        raise KeyError(blank_id)
    return get


def _texter(pattern, selection):
    """Rend une fonction blank_id -> texte C du choix courant."""
    def text(blank_id):
        for opt in pattern.blanks[blank_id][1]:
            if opt.id == selection.get(blank_id):
                return opt.c
        raise KeyError(blank_id)
    return text


def broken_rows(key, params):
    """Sortie reellement produite par le code fautif d'un exercice debug."""
    pattern = PATTERNS[key]
    return pattern.broken(params) if pattern.broken else None


def option_note(key, blank_id, option_id):
    """Explication attachee a un choix, en mode diagnostic."""
    for option in PATTERNS[key].blanks[blank_id][1]:
        if option.id == option_id:
            return option.note
    return ""


def build_trace(key, params, selection):
    """Deroule pas a pas, ou None si le motif n'expose pas de trace."""
    pattern = PATTERNS[key]
    if pattern.trace is None:
        return None
    return pattern.trace(params, _getter(pattern, selection),
                         _texter(pattern, selection))


def build_rows(key, params, selection):
    """Sortie produite par une selection. Leve KeyError si incomplete."""
    pattern = PATTERNS[key]
    return pattern.rows(params, _getter(pattern, selection))


def target_rows(key, params):
    """Sortie cible, produite par la selection de reference."""
    pattern = PATTERNS[key]
    return build_rows(key, params, dict(pattern.ref))


def render_code(key, params, selection=None):
    """Gabarit C, trous remplis par les choix courants."""
    pattern = PATTERNS[key]
    code = pattern.tpl
    for name, value in params.items():
        code = code.replace("@%s@" % name, str(value))
    for blank_id, (_label, options) in pattern.blanks.items():
        text = BLANK_PLACEHOLDER
        chosen = (selection or {}).get(blank_id)
        for opt in options:
            if opt.id == chosen:
                text = opt.c
        code = code.replace("@%s@" % blank_id, text)
    return code



def code_template(key, params):
    """Gabarit avec les tailles substituees, trous laisses en @blank@.

    Le client s'en sert pour rafraichir l'apercu du code a chaque choix,
    sans aller-retour serveur.
    """
    code = PATTERNS[key].tpl
    for name, value in params.items():
        code = code.replace("@%s@" % name, str(value))
    return code


def shuffled_blanks(key, seed):
    """Menus destines au client : l'ordre des options varie par etudiant."""
    pattern = PATTERNS[key]
    out = []
    for blank_id, (label, options) in pattern.blanks.items():
        items = [{"id": o.id, "c": o.c} for o in options]
        random.Random("%s:%s:%s" % (seed, key, blank_id)).shuffle(items)
        out.append({"id": blank_id, "label": label, "options": items})
    return out


def compare(produced, target):
    """Diff ligne a ligne, espaces de fin ignores (cf. fiche projet)."""
    a = [line.rstrip() for line in produced]
    b = [line.rstrip() for line in target]
    height = max(len(a), len(b))
    diff = []
    for idx in range(height):
        left = a[idx] if idx < len(a) else None
        right = b[idx] if idx < len(b) else None
        diff.append({"line": idx + 1, "got": left, "want": right,
                     "ok": left == right})
    return all(d["ok"] for d in diff), diff
