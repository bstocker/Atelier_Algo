"""Module « Les tableaux » : parcours indexé, accumulateurs, recherches."""

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from


def _c_mod(a, b):
    """Le % du C : le reste prend le signe du dividende.

    `-3 % 2` vaut -1 en C, là où Python répond 1. La nuance change le
    résultat d'un test de parité sur des valeurs négatives.
    """
    return a - b * int(a / b)


def _liste(valeurs):
    return "{" + ", ".join(str(v) for v in valeurs) + "}"


# --------------------------------------------------------------------------
# Les jeux de valeurs
# --------------------------------------------------------------------------

def _pas_extremum_en_tete(valeurs):
    """Évite que la première case soit déjà le minimum ou le maximum.

    Sinon la référence initiale n'a jamais besoin d'être remplacée, et des
    conditions pourtant fausses donnent le même résultat que la bonne.
    """
    if valeurs[0] in (min(valeurs), max(valeurs)):
        ordre = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
        milieu = ordre[len(ordre) // 2]
        valeurs[0], valeurs[milieu] = valeurs[milieu], valeurs[0]
    return valeurs


# Séries écrites à la main plutôt que calculées. Une formule produit vite
# des suites où plusieurs conditions fausses donnent la même sortie que la
# bonne — la première case déjà extremum, des négatifs déjà décroissants.
# Ces quatre-là alternent assez pour que chaque distracteur se trahisse.
SEQUENCES = (
    (3, -7, 5, -2, 9, 1, -4, 6),
    (-2, 8, -5, 3, -9, 4, 7, -1),
    (6, 2, -8, 5, -3, 9, -6, 1),
    (4, -1, 7, -6, 2, -9, 8, 3),
)

# Pour « le plus proche de zéro », une paire ±m encadrée de valeurs plus
# éloignées : c'est elle qui rend la règle d'égalité observable. Le négatif
# vient en premier, sinon la règle ne départagerait rien.
SEQUENCES_ZERO = (
    (5, -1, 8, 1, 9, -6, 4, 7),
    (7, -2, 6, 2, 9, 3, -8, 5),
    (4, -3, 9, 3, 7, -5, 8, 6),
    (6, -1, 5, 1, 9, 2, -7, 8),
)


def _melange(p):
    valeurs = _pas_extremum_en_tete(list(SEQUENCES[p["g"]][:p["n"]]))
    return {"t": valeurs, "valeurs": _liste(valeurs)}


def _proche(p):
    valeurs = list(SEQUENCES_ZERO[p["g"]][:p["n"]])
    return {"t": valeurs, "valeurs": _liste(valeurs)}


# Cours choisis pour que la plus forte hausse dépasse la plus forte baisse :
# sans cela, chercher au mauvais endroit donnerait quand même le bon
# résultat, et une réponse fausse serait acceptée.
COURS = (
    (100, 130, 105, 112, 108, 145, 120, 150, 118, 160),
    (90, 124, 101, 118, 96, 138, 112, 150, 108, 142),
    (110, 96, 134, 108, 126, 99, 152, 120, 165, 130),
    (105, 140, 112, 155, 118, 132, 101, 148, 124, 170),
)


def _serie(p):
    cours = list(COURS[p["g"]][:p["n"]])
    return {"t": cours, "valeurs": _liste(cours)}


def _negatifs(p):
    n, g = p["n"], p["g"]
    valeurs = [-(1 + (i * 5 + g * 3) % 23) for i in range(n)]
    return {"t": valeurs, "valeurs": _liste(valeurs)}


# --------------------------------------------------------------------------
# La somme
# --------------------------------------------------------------------------

def _somme_rows(p, get):
    # On affiche l'accumulation tour par tour : deux formules différentes
    # peuvent tomber sur le même total final par hasard, jamais sur la même
    # suite d'états intermédiaires.
    t, expr = p["t"], get("expr")
    total, out = 0, []
    for i, _v in enumerate(t):
        total = expr({"total": total, "t": t, "i": i, "n": len(t)})
        out.append(str(total))
    return out + ["total %d" % total]


SOMME = Pattern(
    key="tab_somme",
    name="La somme d'un tableau",
    brief="Additionner toutes les valeurs saisies dans le tableau.",
    why="Un accumulateur se met à jour à partir de lui-même.",
    lesson=(
        "`t[i]` est la case d'indice `i`. Les indices vont de 0 à `n - 1`.",
        "Un accumulateur part d'une valeur neutre — 0 pour une somme — "
        "**avant** la boucle.",
        "À chaque tour il se met à jour **à partir de sa valeur "
        "précédente** : c'est ce qui le distingue d'une simple affectation.",
    ),
    dims=(("n", 5, 8), ("g", 0, 3)),
    derive=_melange,
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int t[@n@] = @valeurs@;
    int total = 0;
    for (int i = 0; i < n; i++) {
        total = @expr@;
        printf("%d\\n", total);
    }
    printf("total %d\\n", total);
    return 0;
}""",
    blanks={
        "expr": ("Mise à jour de l'accumulateur", _opts(
            ("a", "total + t[i]", lambda c: c["total"] + c["t"][c["i"]]),
            ("b", "t[i]", lambda c: c["t"][c["i"]]),
            ("c", "total + i", lambda c: c["total"] + c["i"]),
            ("d", "total - t[i]", lambda c: c["total"] - c["t"][c["i"]]),
        )),
    },
    ref={"expr": "a"},
    rows=_somme_rows,
    level=1,
)


# --------------------------------------------------------------------------
# Le plus grand et le plus petit
# --------------------------------------------------------------------------

def _extremes_rows(p, get):
    t = p["t"]
    haut, bas = get("cmax"), get("cmin")
    maxi = mini = t[0]
    out = []
    for i in range(1, len(t)):
        ctx = {"t": t, "i": i, "maxi": maxi, "mini": mini}
        if haut(ctx):
            maxi = t[i]
        if bas(ctx):
            mini = t[i]
        out.append("%d %d" % (maxi, mini))
    return out + ["max %d" % maxi, "min %d" % mini]


EXTREMES = Pattern(
    key="tab_extremes",
    name="Le plus grand et le plus petit",
    brief="Trouver la valeur maximale et la valeur minimale du tableau.",
    why="Chercher un extremum, c'est retenir le meilleur vu jusqu'ici.",
    lesson=(
        "On part de la **première case**, pas de zéro : le tableau peut "
        "n'avoir que des valeurs négatives.",
        "La boucle démarre donc à l'indice 1 : la case 0 sert de référence.",
        "À chaque tour, on remplace la référence si la case courante est "
        "meilleure. Rien d'autre.",
    ),
    dims=(("n", 5, 8), ("g", 0, 3)),
    derive=_melange,
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int t[@n@] = @valeurs@;
    int maxi = t[0];
    int mini = t[0];
    for (int i = 1; i < n; i++) {
        if (@cmax@) {
            maxi = t[i];
        }
        if (@cmin@) {
            mini = t[i];
        }
        printf("%d %d\\n", maxi, mini);
    }
    printf("max %d\\n", maxi);
    printf("min %d\\n", mini);
    return 0;
}""",
    blanks={
        "cmax": ("Condition du maximum", _opts(
            ("a", "t[i] > maxi", lambda c: c["t"][c["i"]] > c["maxi"]),
            ("b", "t[i] < maxi", lambda c: c["t"][c["i"]] < c["maxi"]),
            ("c", "t[i] > mini", lambda c: c["t"][c["i"]] > c["mini"]),
            ("d", "t[i] != maxi", lambda c: c["t"][c["i"]] != c["maxi"]),
        )),
        "cmin": ("Condition du minimum", _opts(
            ("a", "t[i] < mini", lambda c: c["t"][c["i"]] < c["mini"]),
            ("b", "t[i] > mini", lambda c: c["t"][c["i"]] > c["mini"]),
            ("c", "t[i] < maxi", lambda c: c["t"][c["i"]] < c["maxi"]),
            ("d", "t[i] != mini", lambda c: c["t"][c["i"]] != c["mini"]),
        )),
    },
    ref={"cmax": "a", "cmin": "a"},
    rows=_extremes_rows,
    level=2,
)


# --------------------------------------------------------------------------
# Pairs et impairs
# --------------------------------------------------------------------------

def _parite_rows(p, get):
    # Le verdict valeur par valeur, et pas seulement les deux totaux : deux
    # conditions différentes peuvent compter pareil sans classer pareil.
    t, test = p["t"], get("cond")
    out, pairs = [], 0
    for i in range(len(t)):
        if test({"t": t, "i": i}):
            out.append("%d pair" % t[i])
            pairs += 1
        else:
            out.append("%d impair" % t[i])
    return out + ["pairs %d" % pairs, "impairs %d" % (len(t) - pairs)]


PARITE = Pattern(
    key="tab_parite",
    name="Combien de pairs, combien d'impairs",
    brief="Compter les valeurs paires et impaires du tableau.",
    why="Le reste d'une division négative ne vaut pas ce qu'on croit.",
    lesson=(
        "En C, le reste prend le **signe du dividende** : `-3 % 2` vaut "
        "`-1`, pas `1`.",
        "Tester `t[i] % 2 == 1` rate donc tous les impairs négatifs.",
        "`t[i] % 2 == 0` reste juste dans les deux cas : zéro n'a pas "
        "de signe.",
    ),
    dims=(("n", 5, 8), ("g", 0, 3)),
    derive=_melange,
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int t[@n@] = @valeurs@;
    int pairs = 0;
    int impairs = 0;
    for (int i = 0; i < n; i++) {
        if (@cond@) {
            printf("%d pair\\n", t[i]);
            pairs++;
        } else {
            printf("%d impair\\n", t[i]);
            impairs++;
        }
    }
    printf("pairs %d\\n", pairs);
    printf("impairs %d\\n", impairs);
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "t[i] % 2 == 0", lambda c: _c_mod(c["t"][c["i"]], 2) == 0),
            ("b", "t[i] % 2 == 1", lambda c: _c_mod(c["t"][c["i"]], 2) == 1),
            ("c", "t[i] % 2 != 0", lambda c: _c_mod(c["t"][c["i"]], 2) != 0),
            ("d", "t[i] > 0", lambda c: c["t"][c["i"]] > 0),
        )),
    },
    ref={"cond": "a"},
    rows=_parite_rows,
    level=2,
)


# --------------------------------------------------------------------------
# La valeur la plus proche de zéro
# --------------------------------------------------------------------------

def _proche_rows(p, get):
    t, test = p["t"], get("cond")
    ref, idx = abs(t[0]), 0
    out = []
    for i in range(1, len(t)):
        if test({"t": t, "i": i, "ref": ref}):
            ref, idx = abs(t[i]), i
        out.append(str(t[idx]))
    return out + ["retenu %d" % t[idx]]


PROCHE_ZERO = Pattern(
    key="tab_proche_zero",
    name="La valeur la plus proche de zéro",
    brief="Trouver la valeur la plus proche de 0. En cas d'égalité, "
          "le positif l'emporte.",
    why="Deux critères : la distance d'abord, le signe pour départager.",
    lesson=(
        "« Proche de zéro » se mesure en **valeur absolue** : `abs(-3)` "
        "et `abs(3)` valent tous deux 3.",
        "Le tableau contient une paire comme -2 et 2 : à distance égale, "
        "l'énoncé demande de garder le positif.",
        "Une seconde condition, reliée par `||`, sert à départager.",
    ),
    dims=(("n", 5, 8), ("g", 0, 3)),
    derive=_proche,
    tpl="""#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int n = @n@;
    int t[@n@] = @valeurs@;
    int ref = abs(t[0]);
    int idx = 0;
    for (int i = 1; i < n; i++) {
        if (@cond@) {
            ref = abs(t[i]);
            idx = i;
        }
        printf("%d\\n", t[idx]);
    }
    printf("retenu %d\\n", t[idx]);
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "abs(t[i]) < ref || (abs(t[i]) == ref && t[i] > 0)",
             lambda c: abs(c["t"][c["i"]]) < c["ref"]
             or (abs(c["t"][c["i"]]) == c["ref"] and c["t"][c["i"]] > 0)),
            ("b", "abs(t[i]) < ref",
             lambda c: abs(c["t"][c["i"]]) < c["ref"]),
            ("c", "t[i] < ref", lambda c: c["t"][c["i"]] < c["ref"]),
            ("d", "abs(t[i]) > ref",
             lambda c: abs(c["t"][c["i"]]) > c["ref"]),
        )),
    },
    ref={"cond": "a"},
    rows=_proche_rows,
    level=3,
)


# --------------------------------------------------------------------------
# La moyenne des valeurs positives
# --------------------------------------------------------------------------

def _moyenne_rows(p, get):
    t = p["t"]
    somme = sum(v for v in t if v > 0)
    combien = sum(1 for v in t if v > 0)
    resultat = get("expr")({"somme": somme, "combien": combien, "n": len(t)})
    return [str(resultat)]


MOYENNE = Pattern(
    key="tab_moyenne",
    name="La moyenne des valeurs positives",
    brief="Faire la moyenne des seules valeurs strictement positives.",
    why="Une moyenne n'a de sens que rapportée au nombre de valeurs retenues.",
    lesson=(
        "Filtrer, c'est compter à part : une somme **et** un compteur.",
        "Diviser par `n` donnerait la moyenne sur tout le tableau, pas sur "
        "les valeurs retenues.",
        "En C, la division de deux `int` est entière : `7 / 2` vaut 3.",
    ),
    dims=(("n", 5, 8), ("g", 0, 3)),
    derive=_melange,
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int t[@n@] = @valeurs@;
    int somme = 0;
    int combien = 0;
    for (int i = 0; i < n; i++) {
        if (t[i] > 0) {
            somme = somme + t[i];
            combien++;
        }
    }
    printf("%d\\n", @expr@);
    return 0;
}""",
    blanks={
        "expr": ("Expression affichée", _opts(
            ("a", "somme / combien", lambda c: int(c["somme"] / c["combien"])),
            ("b", "somme / n", lambda c: int(c["somme"] / c["n"])),
            ("c", "somme", lambda c: c["somme"]),
            # `combien / somme` : l'inverse, une confusion courante. Vaut
            # toujours 0 ici, là où la moyenne vaut au moins 1.
            ("d", "combien / somme",
             lambda c: int(c["combien"] / c["somme"])),
        )),
    },
    ref={"expr": "a"},
    rows=_moyenne_rows,
    level=3,
)


# --------------------------------------------------------------------------
# La plus grande perte
# --------------------------------------------------------------------------

def _perte_rows(p, get):
    # Chaque amélioration est affichée : la trace de la recherche distingue
    # deux parcours qui finiraient par trouver la même valeur.
    cours, n = p["t"], len(p["t"])
    depart, test = get("depart"), get("cond")
    perte, out = 0, []
    for i in range(n):
        for j in range(depart({"i": i, "n": n}), n):
            if test({"cours": cours, "i": i, "j": j, "perte": perte}):
                perte = cours[i] - cours[j]
                out.append("%d %d %d" % (i, j, perte))
    return out + ["perte %d" % perte]


PERTE = Pattern(
    key="tab_perte",
    name="La plus grande perte en bourse",
    brief="Acheter à un instant, revendre plus tard : quelle est la pire perte ?",
    why="On ne peut revendre qu'après avoir acheté. La seconde boucle en dépend.",
    lesson=(
        "Deux boucles imbriquées parcourent **toutes les paires** de dates.",
        "La revente vient après l'achat : la seconde boucle doit démarrer "
        "**après** l'indice de la première.",
        "S'il n'y a jamais de perte, le résultat reste à 0 : c'est la "
        "valeur de départ qui le garantit.",
    ),
    dims=(("n", 6, 10), ("g", 0, 3)),
    derive=_serie,
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int cours[@n@] = @valeurs@;
    int perte = 0;
    for (int i = 0; i < n; i++) {
        for (int j = @depart@; j < n; j++) {
            if (@cond@) {
                perte = cours[i] - cours[j];
                printf("%d %d %d\\n", i, j, perte);
            }
        }
    }
    printf("perte %d\\n", perte);
    return 0;
}""",
    blanks={
        "depart": ("Départ de la seconde boucle", _opts(
            ("a", "i + 1", lambda c: c["i"] + 1),
            ("b", "0", lambda c: 0),
            ("c", "1", lambda c: 1),
            ("d", "n / 2", lambda c: c["n"] // 2),
        )),
        "cond": ("Condition du if", _opts(
            ("a", "cours[i] - cours[j] > perte",
             lambda c: c["cours"][c["i"]] - c["cours"][c["j"]] > c["perte"]),
            ("b", "cours[j] - cours[i] > perte",
             lambda c: c["cours"][c["j"]] - c["cours"][c["i"]] > c["perte"]),
            ("c", "cours[i] > cours[j]",
             lambda c: c["cours"][c["i"]] > c["cours"][c["j"]]),
            ("d", "cours[i] - cours[j] < perte",
             lambda c: c["cours"][c["i"]] - c["cours"][c["j"]] < c["perte"]),
        )),
    },
    ref={"depart": "a", "cond": "a"},
    rows=_perte_rows,
    level=4,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

BUG_MAX_INIT = debug_pattern(
    key="bug_max_init",
    name="Bug : la plus grande valeur",
    but="afficher la plus grande valeur du tableau",
    defaut="maximum initialisé à 0 alors que toutes les valeurs sont négatives",
    dims=(("n", 5, 8), ("g", 0, 3)),
    derive=_negatifs,
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int t[@n@] = @valeurs@;
    int maxi = 0;
    for (int i = 0; i < n; i++) {
        if (t[i] > maxi) {
            maxi = t[i];
        }
    }
    printf("%d\\n", maxi);
    return 0;
}""",
    attendu=lambda p: [str(max(p["t"]))],
    obtenu=lambda p: ["0"],
    diagnostics=(
        ("a", "`maxi` part de 0. Or aucune valeur du tableau n'atteint 0 : "
              "la condition n'est jamais vraie.",
         "Exact. Une recherche de maximum doit partir d'une valeur **du "
         "tableau**, typiquement `t[0]`. Partir de 0 suppose qu'au moins "
         "une valeur est positive — ici, aucune ne l'est."),
        ("b", "La comparaison est inversée : il faudrait `t[i] < maxi`.",
         "Non : cela chercherait le minimum. Et le résultat affiché, 0, "
         "n'appartient toujours pas au tableau."),
        ("c", "La boucle devrait commencer à 1.",
         "Non : commencer à 1 sauterait une case, mais le résultat resterait "
         "0. Le problème est ailleurs, avant la boucle."),
        ("d", "Le `printf` affiche `maxi` au lieu de `t[maxi]`.",
         "Non : `maxi` contient bien une valeur, pas un indice. Le souci "
         "est qu'elle n'a jamais changé."),
    ),
    bonne="a",
    level=3,
)


PREDIRE_EXTREMES = predict_from(
    EXTREMES,
    key="predire_extremes",
    name="Prédire : le plus grand et le plus petit",
    why="Parcourir le tableau de tête, en retenant deux références à la fois.",
    level=3,
    output_format=(
        "MAX MIN",
        "MAX MIN",
        "…",
        "max MAX",
        "min MIN",
    ),
    dims=(("n", 5, 6), ("g", 0, 3)),
)


PATTERNS = (SOMME, EXTREMES, PARITE, PROCHE_ZERO, MOYENNE, PERTE,
            BUG_MAX_INIT, PREDIRE_EXTREMES)

MODULE = Module(
    key="tableaux",
    title="Les tableaux",
    level=2,
    summary="Parcourir un tableau par ses indices : sommes, extremums, "
            "filtres et recherches à deux boucles.",
    keys=tuple(p.key for p in PATTERNS),
)
