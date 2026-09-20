"""Moteur d'exercices « Motifs en C ».

Chaque motif est une donnee : un gabarit de code C troue, des menus
d'options, et une fonction qui reconstruit la sortie ligne a ligne.
Le rendu de la cible et la correction utilisent le meme code, si bien
qu'une selection est juste exactement quand elle reproduit la cible.

Tout est evalue cote serveur : le navigateur ne recoit jamais la
reponse attendue, seulement le motif a obtenir.
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


class InfiniteLoop(Exception):
    """La selection de l'eleve produit une boucle qui ne s'arrete jamais."""


def _never_ends(_ctx):
    raise InfiniteLoop()


@dataclass(frozen=True)
class Option:
    id: str
    c: str            # texte affiche dans le menu et injecte dans le code
    fn: Callable      # semantique : nombre d'iterations, predicat ou valeur


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
    trace: Callable = None                # (params, get, text) -> list[dict]
    lesson: tuple = ()                    # points a retenir, affiches en tete
    level: int = 2                        # cle de LEVELS
    mode: str = "complete"                # complete | predict


def _opts(*triples):
    return [Option(oid, c, fn) for oid, c, fn in triples]


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
# 0. Une ligne d'etoiles — l'exercice d'entree
# --------------------------------------------------------------------------

LIGNE = Pattern(
    key="ligne",
    name="Une ligne d'étoiles",
    brief="Afficher exactement n étoiles, sur une seule ligne.",
    why="Une boucle répète une action. Tout le reste en découle.",
    lesson=(
        "Une boucle `for` tient en trois parties : `for (départ ; test ; pas)`.",
        "`int j = 0` : le compteur démarre à zéro.",
        "`j++` : il avance d'un à chaque tour.",
        "Le test est évalué **avant** chaque tour. Dès qu'il est faux, "
        "la boucle s'arrête.",
        "Le compteur part de 0, donc pour n tours il doit s'arrêter "
        "**avant** d'atteindre n.",
    ),
    dim=("n", 3, 9),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int j = 0; @etoiles@; j++) {
        printf("*");
    }
    printf("\\n");
    return 0;
}""",
    blanks={
        "etoiles": ("Condition d'arrêt de la boucle", _opts(
            ("a", "j < n", lambda c: c["n"]),
            ("b", "j <= n", lambda c: c["n"] + 1),
            ("c", "j < n - 1", lambda c: c["n"] - 1),
            ("d", "j > n", lambda c: 0),
        )),
    },
    ref={"etoiles": "a"},
    rows=lambda p, get: ["*" * get("etoiles")({"n": p["n"]})],
    trace=condition_trace("etoiles", lambda n: 0, +1, "j++"),
    level=1,
)


# --------------------------------------------------------------------------
# 0 bis. Compte a rebours
# --------------------------------------------------------------------------

REBOURS = Pattern(
    key="rebours",
    name="Compte à rebours",
    brief="Afficher n étoiles, mais avec un compteur qui descend.",
    why="Le compteur ne part pas toujours de zéro. La borne change de camp.",
    lesson=(
        "Ici `j` démarre à `n` et **descend** : `j--` retire un à chaque tour.",
        "La boucle s'arrête quand le test devient faux, comme toujours.",
        "Attention au réflexe : ce n'est plus `j < n`. Comptez les valeurs "
        "que prend `j` avant l'arrêt.",
    ),
    dim=("n", 3, 9),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int j = n; @etoiles@; j--) {
        printf("*");
    }
    printf("\\n");
    return 0;
}""",
    blanks={
        "etoiles": ("Condition d'arrêt de la boucle", _opts(
            ("a", "j > 0", lambda c: c["n"]),
            ("b", "j >= 0", lambda c: c["n"] + 1),
            ("c", "j > 1", lambda c: c["n"] - 1),
            ("d", "j < n", lambda c: 0),
        )),
    },
    ref={"etoiles": "a"},
    rows=lambda p, get: ["*" * get("etoiles")({"n": p["n"]})],
    trace=condition_trace("etoiles", lambda n: n, -1, "j--"),
    level=1,
)


# --------------------------------------------------------------------------
# 0 ter. Le pas de la boucle
# --------------------------------------------------------------------------

def _pas_rows(p, get):
    n, pas = p["n"], get("pas")({"n": p["n"]})
    return [" ".join(str(j) for j in range(0, n, pas))]


PAS = Pattern(
    key="pas",
    name="Le pas de la boucle",
    brief="Afficher les nombres de 0 à n-1, de deux en deux.",
    why="Nombre de tours et valeur du compteur sont deux choses distinctes.",
    lesson=(
        "La troisième partie du `for` dit de combien le compteur avance.",
        "`j++` avance de 1, `j += 2` avance de 2.",
        "Changer le pas change **le nombre de tours** et **les valeurs** "
        "prises par `j`. Ici on affiche `j` lui-même, pas une étoile.",
    ),
    dim=("n", 6, 12),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int j = 0; j < n; @pas@) {
        printf("%d ", j);
    }
    printf("\\n");
    return 0;
}""",
    blanks={
        "pas": ("Pas de la boucle", _opts(
            ("a", "j += 2", lambda c: 2),
            ("b", "j++", lambda c: 1),
            ("c", "j += 3", lambda c: 3),
            ("d", "j += 5", lambda c: 5),
        )),
    },
    ref={"pas": "a"},
    rows=_pas_rows,
    trace=step_trace(
        "pas", "j < n",
        {"j++": lambda n: 1, "j += 2": lambda n: 2,
         "j += 3": lambda n: 3, "j += 5": lambda n: 5},
        emit=lambda j: "%d " % j,
        action='printf("%d ", j)',
    ),
    level=2,
)


# --------------------------------------------------------------------------
# 0 quater. La boucle while et l'increment oublie
# --------------------------------------------------------------------------

WHILE = Pattern(
    key="tantque",
    name="La boucle while",
    brief="Le même comptage, écrit avec while. À vous de faire avancer j.",
    why="Le for cache l'incrément. Le while le laisse à votre charge.",
    lesson=(
        "`while (test)` répète tant que le test est vrai — exactement comme "
        "le `for`, mais sans son départ ni son pas.",
        "C'est à vous d'écrire ce qui fait avancer le compteur, **dans** "
        "le corps de la boucle.",
        "Si rien ne rapproche le compteur de la condition d'arrêt, le test "
        "reste vrai : la boucle ne s'arrête jamais.",
    ),
    dim=("n", 4, 9),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int j = 0;
    while (j < n) {
        printf("*");
        @incr@;
    }
    printf("\\n");
    return 0;
}""",
    blanks={
        "incr": ("Ce qui fait avancer le compteur", _opts(
            ("a", "j++", lambda c: c["n"]),
            ("b", "j += 2", lambda c: -(-c["n"] // 2)),
            ("c", "j += n", lambda c: 1),
            ("d", "j--", _never_ends),
        )),
    },
    ref={"incr": "a"},
    rows=lambda p, get: ["*" * get("incr")({"n": p["n"]})],
    trace=step_trace(
        "incr", "j < n",
        {"j++": lambda n: 1, "j += 2": lambda n: 2,
         "j += n": lambda n: n, "j--": lambda n: -1},
        emit=lambda _j: "*",
        action='printf("*")',
    ),
    level=2,
)


# --------------------------------------------------------------------------
# 1. Carre
# --------------------------------------------------------------------------

CARRE = Pattern(
    key="carre",
    name="Carré",
    brief="Un carré plein de n lignes sur n colonnes.",
    why="La boucle interne ne dépend pas de la ligne courante.",
    dim=("n", 3, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++) {
        for (int j = 0; @stars@; j++) {
            printf("*");
        }
        printf("\\n");
    }
    return 0;
}""",
    blanks={
        "stars": ("Condition de la boucle des étoiles", _opts(
            ("a", "j < n", lambda c: c["n"]),
            ("b", "j < i", lambda c: c["i"]),
            ("c", "j <= i", lambda c: c["i"] + 1),
            ("d", "j < n - i", lambda c: c["n"] - c["i"]),
        )),
    },
    ref={"stars": "a"},
    rows=lambda p, get: [
        "*" * get("stars")({"i": i, "n": p["n"]}) for i in range(p["n"])
    ],
    level=2,
)


# --------------------------------------------------------------------------
# 2. Triangle rectangle
# --------------------------------------------------------------------------

TRIANGLE_RECT = Pattern(
    key="triangle_rect",
    name="Triangle rectangle",
    brief="Une étoile de plus à chaque ligne, aligné à gauche.",
    why="La boucle interne dépend de la ligne courante.",
    dim=("n", 3, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++) {
        for (int j = 0; @stars@; j++) {
            printf("*");
        }
        printf("\\n");
    }
    return 0;
}""",
    blanks={
        "stars": ("Condition de la boucle des étoiles", _opts(
            ("a", "j < n", lambda c: c["n"]),
            ("b", "j <= i", lambda c: c["i"] + 1),
            ("c", "j < i", lambda c: c["i"]),
            ("d", "j <= n - i", lambda c: c["n"] - c["i"] + 1),
        )),
    },
    ref={"stars": "b"},
    rows=lambda p, get: [
        "*" * get("stars")({"i": i, "n": p["n"]}) for i in range(p["n"])
    ],
    level=2,
)


# --------------------------------------------------------------------------
# 3. Triangle inverse
# --------------------------------------------------------------------------

TRIANGLE_INV = Pattern(
    key="triangle_inv",
    name="Triangle inversé",
    brief="On part de n étoiles et on en retire une à chaque ligne.",
    why="Le compte décroît : la borne se calcule à partir de n et de i.",
    dim=("n", 3, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++) {
        for (int j = 0; @stars@; j++) {
            printf("*");
        }
        printf("\\n");
    }
    return 0;
}""",
    blanks={
        "stars": ("Condition de la boucle des étoiles", _opts(
            ("a", "j < n - i", lambda c: c["n"] - c["i"]),
            ("b", "j < n - i - 1", lambda c: c["n"] - c["i"] - 1),
            ("c", "j <= n - i", lambda c: c["n"] - c["i"] + 1),
            ("d", "j <= i", lambda c: c["i"] + 1),
        )),
    },
    ref={"stars": "a"},
    rows=lambda p, get: [
        "*" * get("stars")({"i": i, "n": p["n"]}) for i in range(p["n"])
    ],
    level=2,
)


# --------------------------------------------------------------------------
# 4. Triangle aligne a droite
# --------------------------------------------------------------------------

TRIANGLE_DROITE = Pattern(
    key="triangle_droite",
    name="Triangle aligné à droite",
    brief="Même triangle, mais poussé contre le bord droit par des espaces.",
    why="Deux boucles internes se partagent la ligne : espaces puis étoiles.",
    dim=("n", 3, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++) {
        for (int j = 0; @spaces@; j++) {
            printf(" ");
        }
        for (int j = 0; @stars@; j++) {
            printf("*");
        }
        printf("\\n");
    }
    return 0;
}""",
    blanks={
        "spaces": ("Condition de la boucle des espaces", _opts(
            ("a", "j < n - 1 - i", lambda c: c["n"] - 1 - c["i"]),
            ("b", "j < n - i", lambda c: c["n"] - c["i"]),
            ("c", "j < i", lambda c: c["i"]),
            ("d", "j <= n - i", lambda c: c["n"] - c["i"] + 1),
        )),
        "stars": ("Condition de la boucle des étoiles", _opts(
            ("a", "j <= i", lambda c: c["i"] + 1),
            ("b", "j < i", lambda c: c["i"]),
            ("c", "j < n", lambda c: c["n"]),
            ("d", "j < n - i", lambda c: c["n"] - c["i"]),
        )),
    },
    ref={"spaces": "a", "stars": "a"},
    rows=lambda p, get: [
        " " * get("spaces")({"i": i, "n": p["n"]})
        + "*" * get("stars")({"i": i, "n": p["n"]})
        for i in range(p["n"])
    ],
    level=3,
)


# --------------------------------------------------------------------------
# 5. Losange
# --------------------------------------------------------------------------

def _losange_rows(p, get):
    h = p["h"]
    out = []
    for i in range(2 * h):
        L = i if i < h else 2 * h - 1 - i
        ctx = {"i": i, "h": h, "L": L}
        out.append(" " * get("spaces")(ctx) + "*" * get("stars")(ctx))
    return out


LOSANGE = Pattern(
    key="losange",
    name="Losange",
    brief="2 × h lignes. L monte de 0 à h-1 puis redescend symétriquement.",
    why="Une variable intermédiaire (L) évite d'écrire deux boucles séparées.",
    dim=("h", 2, 5),
    tpl="""#include <stdio.h>

int main(void) {
    int h = @h@;
    for (int i = 0; i < 2 * h; i++) {
        int L = (i < h) ? i : (2 * h - 1 - i);
        for (int j = 0; @spaces@; j++) {
            printf(" ");
        }
        for (int j = 0; @stars@; j++) {
            printf("*");
        }
        printf("\\n");
    }
    return 0;
}""",
    blanks={
        "spaces": ("Condition de la boucle des espaces", _opts(
            ("a", "j < h - 1 - L", lambda c: c["h"] - 1 - c["L"]),
            ("b", "j < h - L", lambda c: c["h"] - c["L"]),
            ("c", "j < L", lambda c: c["L"]),
            ("d", "j < h - 1 - i", lambda c: max(0, c["h"] - 1 - c["i"])),
        )),
        "stars": ("Condition de la boucle des étoiles", _opts(
            ("a", "j < 2 * (L + 1)", lambda c: 2 * (c["L"] + 1)),
            ("b", "j < 2 * L + 1", lambda c: 2 * c["L"] + 1),
            ("c", "j < L + 1", lambda c: c["L"] + 1),
            ("d", "j < 2 * h", lambda c: 2 * c["h"]),
        )),
    },
    ref={"spaces": "a", "stars": "a"},
    rows=_losange_rows,
    level=4,
)


# --------------------------------------------------------------------------
# 6. Pyramide
# --------------------------------------------------------------------------

PYRAMIDE = Pattern(
    key="pyramide",
    name="Pyramide",
    brief='Chaque étoile est suivie d\'un espace : on imprime des groupes "* ".',
    why="Le motif se lit en groupes, pas en caractères isolés.",
    dim=("n", 3, 7),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++) {
        for (int j = 0; @spaces@; j++) {
            printf(" ");
        }
        for (int k = 0; @groups@; k++) {
            printf("* ");
        }
        printf("\\n");
    }
    return 0;
}""",
    blanks={
        "spaces": ("Condition de la boucle des espaces", _opts(
            ("a", "j < n - 1 - i", lambda c: c["n"] - 1 - c["i"]),
            ("b", "j < n - i", lambda c: c["n"] - c["i"]),
            ("c", "j < i", lambda c: c["i"]),
            ("d", "j < 2 * i", lambda c: 2 * c["i"]),
        )),
        "groups": ('Condition de la boucle des groupes "* "', _opts(
            ("a", "k <= i", lambda c: c["i"] + 1),
            ("b", "k < i", lambda c: c["i"]),
            ("c", "k < n", lambda c: c["n"]),
            ("d", "k <= 2 * i", lambda c: 2 * c["i"] + 1),
        )),
    },
    ref={"spaces": "a", "groups": "a"},
    rows=lambda p, get: [
        (" " * get("spaces")({"i": i, "n": p["n"]})
         + "* " * get("groups")({"i": i, "n": p["n"]})).rstrip()
        for i in range(p["n"])
    ],
    level=3,
)


# --------------------------------------------------------------------------
# 7. Carre magique
# --------------------------------------------------------------------------

def _magique_rows(p, get):
    n = p["n"]
    pred = get("border")
    out = []
    for i in range(n):
        out.append("".join(
            "*" if pred({"i": i, "j": j, "n": n}) else "o" for j in range(n)
        ))
    return out


CARRE_MAGIQUE = Pattern(
    key="carre_magique",
    name="Carré magique",
    brief="Un carré dont seul le bord est en étoiles, l'intérieur en o.",
    why="Le if introduit une décision à l'intérieur des deux boucles.",
    dim=("n", 3, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (@border@) {
                printf("*");
            } else {
                printf("o");
            }
        }
        printf("\\n");
    }
    return 0;
}""",
    blanks={
        "border": ("Condition du if", _opts(
            ("a", "i == 0 || i == n - 1 || j == 0 || j == n - 1",
             lambda c: c["i"] == 0 or c["i"] == c["n"] - 1
             or c["j"] == 0 or c["j"] == c["n"] - 1),
            ("b", "i == 0 && i == n - 1 && j == 0 && j == n - 1",
             lambda c: c["i"] == 0 and c["i"] == c["n"] - 1
             and c["j"] == 0 and c["j"] == c["n"] - 1),
            ("c", "i == 0 || j == 0",
             lambda c: c["i"] == 0 or c["j"] == 0),
            ("d", "i == j || i + j == n - 1",
             lambda c: c["i"] == c["j"] or c["i"] + c["j"] == c["n"] - 1),
        )),
    },
    ref={"border": "a"},
    rows=_magique_rows,
    level=3,
)


# --------------------------------------------------------------------------
# 8. Table de multiplication
# --------------------------------------------------------------------------

def _table_rows(p, get):
    v = p["v"]
    count = get("bound")({"v": v})
    expr = get("product")
    return [
        "%d x %d = %d" % (v, k, expr({"v": v, "k": k}))
        for k in range(1, count + 1)
    ]


TABLE = Pattern(
    key="table",
    name="Table de multiplication",
    brief="La table de v, de 1 à 9. La valeur v est saisie au clavier.",
    why="Première entrée utilisateur : la sortie dépend d'une donnée lue.",
    # v reste sous 10 : a v = 10, le distracteur `k < v` produirait les memes
    # 9 lignes que la bonne reponse `k <= 9`, et serait accepte a tort.
    value=("v", 2, 9),
    tpl="""#include <stdio.h>

int main(void) {
    int v;
    scanf("%d", &v);          /* l'utilisateur a saisi @v@ */
    for (int k = 1; @bound@; k++) {
        printf("%d x %d = %d\\n", v, k, @product@);
    }
    return 0;
}""",
    blanks={
        "bound": ("Condition de la boucle", _opts(
            ("a", "k <= 9", lambda c: 9),
            ("b", "k < 9", lambda c: 8),
            ("c", "k <= 10", lambda c: 10),
            ("d", "k < v", lambda c: max(0, c["v"] - 1)),
        )),
        "product": ("Expression du produit", _opts(
            ("a", "v * k", lambda c: c["v"] * c["k"]),
            ("b", "k * k", lambda c: c["k"] * c["k"]),
            ("c", "v + k", lambda c: c["v"] + c["k"]),
            ("d", "v * v", lambda c: c["v"] * c["v"]),
        )),
    },
    ref={"bound": "a", "product": "a"},
    rows=_table_rows,
    level=3,
)


# --------------------------------------------------------------------------
# Mode « predire la sortie »
# --------------------------------------------------------------------------

def predict_from(base, key, name, why, level, dim=None):
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
        level=level,
        mode="predict",
    )


PREDIRE_TRIANGLE = predict_from(
    TRIANGLE_DROITE,
    key="predire_triangle",
    name="Prédire : triangle aligné à droite",
    why="Deux boucles se partagent la ligne. Comptez les espaces avant les étoiles.",
    level=3,
    dim=("n", 3, 6),
)

PREDIRE_MAGIQUE = predict_from(
    CARRE_MAGIQUE,
    key="predire_magique",
    name="Prédire : carré magique",
    why="Un if dans deux boucles : la sortie dépend de la position, pas du compteur seul.",
    level=4,
    dim=("n", 3, 6),
)


PATTERNS = {
    p.key: p
    for p in (LIGNE, REBOURS, PAS, WHILE,
              CARRE, TRIANGLE_RECT, TRIANGLE_INV, TRIANGLE_DROITE,
              LOSANGE, PYRAMIDE, CARRE_MAGIQUE, TABLE,
              PREDIRE_TRIANGLE, PREDIRE_MAGIQUE)
}

ALL_KEYS = list(PATTERNS)


# --------------------------------------------------------------------------
# Generation, rendu et correction
# --------------------------------------------------------------------------

def draw_params(key, rng=None):
    """Tire la taille (ou la valeur saisie) d'un exercice."""
    rng = rng or random
    pattern = PATTERNS[key]
    spec = pattern.dim or pattern.value
    name, lo, hi = spec
    return {name: rng.randint(lo, hi)}


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
