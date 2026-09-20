"""Module « Les conditions » : comparaisons, opérateurs logiques, switch."""

from ..engine import Module, Pattern, _diag, _opts, debug_pattern, predict_from

JOURS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi")


# --------------------------------------------------------------------------
# Le joueur qui gagne
# --------------------------------------------------------------------------

def _gagnant_rows(p, get):
    n = p["n"]
    s2 = n // 2 + 1
    premier, second = get("c1"), get("c2")
    out = []
    for s1 in range(1, n + 1):
        ctx = {"s1": s1, "s2": s2}
        if premier(ctx):
            verdict = "Joueur 1 gagne"
        elif second(ctx):
            verdict = "Joueur 2 gagne"
        else:
            verdict = "Egalite"
        out.append("%d-%d : %s" % (s1, s2, verdict))
    return out


GAGNANT = Pattern(
    key="cond_gagnant",
    name="Le joueur qui gagne",
    brief="Comparer deux scores et désigner le vainqueur, ou l'égalité.",
    why="Trois issues, donc deux tests enchaînés et un cas restant.",
    lesson=(
        "`if … else if … else` teste **dans l'ordre** : dès qu'une condition "
        "est vraie, les suivantes ne sont pas évaluées.",
        "Le dernier `else` ramasse tout ce qui reste. Ici, l'égalité.",
        "`>` exclut l'égalité, `>=` l'inclut. C'est toute la différence "
        "entre « gagne » et « ne perd pas ».",
    ),
    dim=("n", 4, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int s2 = n / 2 + 1;              /* le score du joueur 2 */
    for (int s1 = 1; s1 <= n; s1++) {
        printf("%d-%d : ", s1, s2);
        if (@c1@) {
            printf("Joueur 1 gagne\\n");
        } else if (@c2@) {
            printf("Joueur 2 gagne\\n");
        } else {
            printf("Egalite\\n");
        }
    }
    return 0;
}""",
    blanks={
        "c1": ("Premier test", _opts(
            ("a", "s1 > s2", lambda c: c["s1"] > c["s2"]),
            ("b", "s1 < s2", lambda c: c["s1"] < c["s2"]),
            ("c", "s1 >= s2", lambda c: c["s1"] >= c["s2"]),
            ("d", "s1 == s2", lambda c: c["s1"] == c["s2"]),
        )),
        "c2": ("Second test", _opts(
            ("a", "s1 < s2", lambda c: c["s1"] < c["s2"]),
            ("b", "s1 > s2", lambda c: c["s1"] > c["s2"]),
            ("c", "s1 <= s2", lambda c: c["s1"] <= c["s2"]),
            ("d", "s2 - s1 > 1", lambda c: c["s2"] - c["s1"] > 1),
        )),
    },
    ref={"c1": "a", "c2": "a"},
    rows=_gagnant_rows,
    level=1,
)


# --------------------------------------------------------------------------
# Pair ou impair
# --------------------------------------------------------------------------

PARITE = Pattern(
    key="cond_parite",
    name="Pair ou impair",
    brief="Dire de chaque nombre de 1 à n s'il est pair ou impair.",
    why="Le reste de la division par 2 est la seule information utile.",
    lesson=(
        "`%` donne le **reste** d'une division entière : `7 % 2` vaut 1.",
        "Un nombre est pair quand ce reste est nul.",
        "Attention : `/` donne le quotient, pas le reste. `7 / 2` vaut 3.",
    ),
    dim=("n", 4, 9),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 1; i <= n; i++) {
        if (@cond@) {
            printf("%d pair\\n", i);
        } else {
            printf("%d impair\\n", i);
        }
    }
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "i % 2 == 0", lambda c: c["i"] % 2 == 0),
            ("b", "i % 2 == 1", lambda c: c["i"] % 2 == 1),
            ("c", "i / 2 == 0", lambda c: c["i"] // 2 == 0),
            ("d", "i % 3 == 0", lambda c: c["i"] % 3 == 0),
        )),
    },
    ref={"cond": "a"},
    rows=lambda p, get: [
        "%d %s" % (i, "pair" if get("cond")({"i": i}) else "impair")
        for i in range(1, p["n"] + 1)
    ],
    level=1,
)


# --------------------------------------------------------------------------
# C est-il compris entre A et B ?
# --------------------------------------------------------------------------

def _entre_rows(p, get):
    a, b = p["n"], p["n"] + 6
    test = get("cond")
    return ["%d : %s" % (c, "oui" if test({"a": a, "b": b, "c": c}) else "non")
            for c in range(a - 2, b + 3)]


ENTRE = Pattern(
    key="cond_entre",
    name="C entre A et B",
    brief="Dire si C tombe strictement entre A et B, avec A plus petit que B.",
    why="Deux comparaisons à combiner : le et logique.",
    lesson=(
        "`&&` est vrai quand **les deux** côtés le sont.",
        "`||` est vrai dès qu'**un seul** côté l'est.",
        "« Entre A et B » demande deux conditions à la fois : plus grand "
        "que A **et** plus petit que B.",
    ),
    dim=("n", 5, 12),
    tpl="""#include <stdio.h>

int main(void) {
    int a = @n@;
    int b = @n@ + 6;
    for (int c = a - 2; c <= b + 2; c++) {
        printf("%d : ", c);
        if (@cond@) {
            printf("oui\\n");
        } else {
            printf("non\\n");
        }
    }
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "c > a && c < b", lambda x: x["c"] > x["a"] and x["c"] < x["b"]),
            ("b", "c >= a && c <= b", lambda x: x["a"] <= x["c"] <= x["b"]),
            ("c", "c > a || c < b", lambda x: x["c"] > x["a"] or x["c"] < x["b"]),
            ("d", "c > a && c > b", lambda x: x["c"] > x["a"] and x["c"] > x["b"]),
        )),
    },
    ref={"cond": "a"},
    rows=_entre_rows,
    level=2,
)


# --------------------------------------------------------------------------
# C entre A et B, dans un ordre ou dans l'autre
# --------------------------------------------------------------------------

def _entre_ordre_rows(p, get):
    n = p["n"]
    test = get("cond")
    out = []
    for a, b in ((n, n + 5), (n + 5, n)):
        for c in range(n - 1, n + 7):
            verdict = "oui" if test({"a": a, "b": b, "c": c}) else "non"
            out.append("a=%d b=%d c=%d : %s" % (a, b, c, verdict))
    return out


ENTRE_ORDRE = Pattern(
    key="cond_entre_ordre",
    name="C entre A et B, sans savoir lequel est le plus grand",
    brief="Même question, mais A peut aussi bien être au-dessus de B.",
    why="Il faut couvrir les deux dispositions, d'où un ou logique de deux et.",
    lesson=(
        "On ne sait plus lequel de A ou B est le plus petit.",
        "Deux cas possibles, donc deux conditions reliées par `||`.",
        "Les parenthèses comptent : `&&` lie plus fort que `||`, mais les "
        "écrire rend l'intention lisible.",
    ),
    dim=("n", 4, 10),
    tpl="""#include <stdio.h>

int main(void) {
    int bornes[2][2] = { {@n@, @n@ + 5}, {@n@ + 5, @n@} };
    for (int t = 0; t < 2; t++) {
        int a = bornes[t][0];
        int b = bornes[t][1];
        for (int c = @n@ - 1; c < @n@ + 7; c++) {
            printf("a=%d b=%d c=%d : ", a, b, c);
            if (@cond@) {
                printf("oui\\n");
            } else {
                printf("non\\n");
            }
        }
    }
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "(c > a && c < b) || (c < a && c > b)",
             lambda x: (x["c"] > x["a"] and x["c"] < x["b"])
             or (x["c"] < x["a"] and x["c"] > x["b"])),
            ("b", "c > a && c < b",
             lambda x: x["c"] > x["a"] and x["c"] < x["b"]),
            ("c", "(c >= a && c <= b) || (c <= a && c >= b)",
             lambda x: (x["a"] <= x["c"] <= x["b"])
             or (x["b"] <= x["c"] <= x["a"])),
            ("d", "c > a || c < b", lambda x: x["c"] > x["a"] or x["c"] < x["b"]),
        )),
    },
    ref={"cond": "a"},
    rows=_entre_ordre_rows,
    level=3,
)


# --------------------------------------------------------------------------
# Le switch
# --------------------------------------------------------------------------

SWITCH = Pattern(
    key="cond_switch",
    name="La parité avec un switch",
    brief="Même question que « pair ou impair », mais avec un switch.",
    why="Un switch compare une valeur à des cas : c'est l'expression qui porte le calcul.",
    lesson=(
        "`switch (expression)` compare le résultat de l'expression à chaque "
        "`case`.",
        "`default` joue le rôle du `else` : il attrape tout le reste.",
        "Un `case` ne teste pas une condition, seulement une **valeur**. "
        "Le calcul doit donc être dans l'expression du switch.",
    ),
    dim=("n", 4, 9),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int v = 1; v <= n; v++) {
        switch (@expr@) {
            case 0:
                printf("%d pair\\n", v);
                break;
            default:
                printf("%d impair\\n", v);
        }
    }
    return 0;
}""",
    blanks={
        "expr": ("Expression du switch", _opts(
            ("a", "v % 2", lambda c: c["v"] % 2),
            ("b", "v / 2", lambda c: c["v"] // 2),
            ("c", "v % 3", lambda c: c["v"] % 3),
            ("d", "v % 2 == 0", lambda c: 1 if c["v"] % 2 == 0 else 0),
        )),
    },
    ref={"expr": "a"},
    rows=lambda p, get: [
        "%d %s" % (v, "pair" if get("expr")({"v": v}) == 0 else "impair")
        for v in range(1, p["n"] + 1)
    ],
    level=2,
)


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------

BUG_AFFECTATION = debug_pattern(
    key="bug_affectation",
    name="Bug : pair ou impair",
    but="dire de chaque nombre de 1 à n s'il est pair ou impair",
    defaut="= au lieu de == : une affectation, pas une comparaison",
    dim=("n", 4, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 1; i <= n; i++) {
        int reste = i % 2;
        if (reste = 0) {
            printf("%d pair\\n", i);
        } else {
            printf("%d impair\\n", i);
        }
    }
    return 0;
}""",
    attendu=lambda p: ["%d %s" % (i, "pair" if i % 2 == 0 else "impair")
                       for i in range(1, p["n"] + 1)],
    obtenu=lambda p: ["%d impair" % i for i in range(1, p["n"] + 1)],
    diagnostics=(
        ("a", "`reste = 0` **affecte** 0 à `reste` au lieu de le comparer. "
              "La condition vaut donc 0, c'est-à-dire faux, à chaque tour.",
         "Exact. En C, `=` affecte et `==` compare. Une affectation est une "
         "expression dont la valeur est celle affectée : ici 0, donc faux. "
         "Le C accepte ce code sans broncher, d'où le piège."),
        ("b", "Le reste devrait se calculer avec `/` et non `%`.",
         "Non : `i % 2` est bien le reste, et il est correct. Regardez ce "
         "que la condition fait de ce reste."),
        ("c", "La boucle devrait commencer à 0.",
         "Non : le nombre de lignes est bon et les valeurs affichées aussi. "
         "Seul le verdict est faux, et il l'est partout."),
        ("d", "Les deux `printf` sont inversés.",
         "Non : les inverser donnerait « pair » partout, ce qui serait tout "
         "aussi faux. Le verdict ne change jamais, c'est cela l'indice."),
    ),
    bonne="a",
    level=2,
)


def _break_cases(p):
    return {"cases": "\n".join(
        '            case %d:\n                printf("%s\\\\n");' % (i + 1, jour)
        for i, jour in enumerate(JOURS[:p["n"]]))}


BUG_BREAK = debug_pattern(
    key="bug_break",
    name="Bug : le nom du jour",
    but="afficher le nom du jour correspondant à chaque numéro",
    defaut="break manquant : les cas suivants s'exécutent en cascade",
    dim=("n", 3, 5),
    derive=_break_cases,
    tpl="""#include <stdio.h>

int main(void) {
    for (int jour = 1; jour <= @n@; jour++) {
        switch (jour) {
@cases@
        }
    }
    return 0;
}""",
    attendu=lambda p: list(JOURS[:p["n"]]),
    obtenu=lambda p: [JOURS[j] for i in range(p["n"])
                      for j in range(i, p["n"])],
    diagnostics=(
        ("a", "Sans `break`, l'exécution continue dans les `case` suivants : "
              "elle ne s'arrête pas au cas trouvé.",
         "Exact. Un `case` est une étiquette d'entrée, pas un bloc fermé. "
         "Sans `break`, tout ce qui suit s'exécute — c'est le « fall-through », "
         "utile parfois, piégeux ici."),
        ("b", "Les `case` sont dans le mauvais ordre.",
         "Non : le premier jour affiché est bien le bon à chaque tour. "
         "Ce sont les lignes **en trop** qui posent problème."),
        ("c", "Il manque un `default`.",
         "Non : toutes les valeurs de `jour` ont leur `case`. Un `default` "
         "ne changerait rien à ce qui s'affiche."),
        ("d", "La boucle va une fois de trop.",
         "Non : comptez les premières lignes de chaque tour, elles sont "
         "justes. Le surplus vient de l'intérieur du switch."),
    ),
    bonne="a",
    level=3,
)


# --------------------------------------------------------------------------
# Prédiction
# --------------------------------------------------------------------------

PREDIRE_GAGNANT = predict_from(
    GAGNANT,
    key="predire_gagnant",
    name="Prédire : le joueur qui gagne",
    why="Trois branches à dérouler pour chaque valeur du compteur.",
    level=3,
    dim=("n", 4, 6),
)


PATTERNS = (GAGNANT, PARITE, ENTRE, SWITCH, ENTRE_ORDRE,
            BUG_AFFECTATION, BUG_BREAK, PREDIRE_GAGNANT)

MODULE = Module(
    key="conditions",
    title="Les conditions",
    level=1,
    summary="Comparer, combiner avec et / ou, enchaîner des if, "
            "et distribuer les cas avec un switch.",
    keys=tuple(p.key for p in PATTERNS),
)
