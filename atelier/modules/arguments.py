"""Module « Les arguments » : ce que le programme reçoit de la ligne de commande.

En C, `main` peut déclarer `int argc, char *argv[]`. `argv[0]` est le nom
du programme lui-même : les arguments de l'utilisateur commencent à 1.
C'est de là que vient la plupart des erreurs de ce module.
"""

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from

# Jeux d'arguments. Le négatif d'une paire ±m arrive avant le positif,
# sinon la règle d'égalité de « la plus proche de zéro » ne départagerait
# rien. Aucune valeur n'est le maximum ni le minimum en première position.
JEUX = (
    (5, -1, 8, 1, 9, -6),
    (7, -2, 6, 2, 9, 3),
    (4, -3, 9, 3, 7, -5),
    (6, -1, 5, 1, 9, 2),
)


def _jeu(p):
    valeurs = list(JEUX[p["g"]][:p["n"]])
    return {"args": valeurs,
            "ligne": " ".join(str(v) for v in valeurs),
            "argc": len(valeurs) + 1}


def _jeu_moyenne(p):
    """Un jeu dont la somme est un multiple exact du nombre d'arguments.

    La division entière écrase les petits écarts : sans cette précaution,
    `somme / argc` et `somme / (argc - 1)` tomberaient parfois sur le même
    résultat, et le bug serait invisible.
    """
    n, g = p["n"], p["g"]
    valeurs = list(JEUX[g][:n])
    valeurs[-1] += n * (3 + g % 3) - sum(valeurs)
    return {"args": valeurs,
            "ligne": " ".join(str(v) for v in valeurs),
            "argc": len(valeurs) + 1}


def _carre(p):
    return {"ligne": str(p["v"])}


# --------------------------------------------------------------------------
# Le carré d'un argument
# --------------------------------------------------------------------------

CARRE = Pattern(
    key="arg_carre",
    name="Le carré d'un argument",
    brief="Le programme reçoit un nombre et affiche son carré.",
    why="Un argument arrive sous forme de texte : il faut le convertir.",
    lesson=(
        "`argv[1]` est le **premier argument de l'utilisateur**. "
        "`argv[0]` contient le nom du programme.",
        "C'est une chaîne de caractères : `\"5\"`, pas `5`.",
        "`atoi` (*ASCII to integer*) la convertit en entier. Sans cela, "
        "on multiplierait des adresses.",
    ),
    value=("v", 3, 12),
    derive=_carre,
    tpl="""/* Lancé par :  ./programme @ligne@ */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    int v = atoi(argv[1]);
    printf("%d\\n", @expr@);
    return 0;
}""",
    blanks={
        "expr": ("Expression affichée", _opts(
            ("a", "v * v", lambda c: c["v"] * c["v"]),
            ("b", "v + v", lambda c: c["v"] + c["v"]),
            ("c", "v * 2", lambda c: c["v"] * 2),
            ("d", "v", lambda c: c["v"]),
        )),
    },
    ref={"expr": "a"},
    rows=lambda p, get: [str(get("expr")({"v": p["v"]}))],
    level=1,
)


# --------------------------------------------------------------------------
# Combien d'arguments ?
# --------------------------------------------------------------------------

COMBIEN = Pattern(
    key="arg_combien",
    name="Combien d'arguments",
    brief="Afficher le nombre d'arguments passés par l'utilisateur.",
    why="argc compte aussi le nom du programme. Un de plus qu'on ne croit.",
    lesson=(
        "`argc` est le nombre d'entrées de `argv`, **nom du programme "
        "compris**.",
        "Lancer `./programme 5 12` donne donc `argc == 3`.",
        "Le nombre d'arguments de l'utilisateur est `argc - 1`.",
    ),
    dims=(("n", 3, 6), ("g", 0, 3)),
    derive=_jeu,
    tpl="""/* Lancé par :  ./programme @ligne@ */
#include <stdio.h>

int main(int argc, char *argv[]) {
    printf("%d\\n", @expr@);
    return 0;
}""",
    blanks={
        "expr": ("Expression affichée", _opts(
            ("a", "argc - 1", lambda c: c["argc"] - 1),
            ("b", "argc", lambda c: c["argc"]),
            ("c", "argc + 1", lambda c: c["argc"] + 1),
            ("d", "argc - 2", lambda c: c["argc"] - 2),
        )),
    },
    ref={"expr": "a"},
    rows=lambda p, get: [str(get("expr")({"argc": p["argc"]}))],
    level=1,
)


# --------------------------------------------------------------------------
# La somme des arguments
# --------------------------------------------------------------------------

def _somme_rows(p, get):
    args, argc = p["args"], p["argc"]
    debut = get("depart")({"argc": argc})
    total, out = 0, []
    for i in range(debut, argc):
        total += args[i - 1] if i >= 1 else 0     # argv[0] : atoi("./…") = 0
        out.append(str(total))
    return out + ["total %d" % total]


SOMME = Pattern(
    key="arg_somme",
    name="La somme des arguments",
    brief="Additionner tous les nombres passés en ligne de commande.",
    why="Le parcours doit sauter argv[0], qui n'est pas un nombre.",
    lesson=(
        "Parcourir les arguments, c'est boucler de 1 à `argc - 1`.",
        "Démarrer à 0 fait passer le nom du programme dans `atoi`, qui "
        "rend 0 : la somme ne change pas, mais un tour de trop a lieu.",
        "`atoi` rend 0 pour tout texte qu'il ne sait pas lire. Il ne "
        "signale jamais d'erreur.",
    ),
    dims=(("n", 3, 6), ("g", 0, 3)),
    derive=_jeu,
    tpl="""/* Lancé par :  ./programme @ligne@ */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    int total = 0;
    for (int i = @depart@; i < argc; i++) {
        total = total + atoi(argv[i]);
        printf("%d\\n", total);
    }
    printf("total %d\\n", total);
    return 0;
}""",
    blanks={
        "depart": ("Départ de la boucle", _opts(
            ("a", "1", lambda c: 1),
            ("b", "0", lambda c: 0),
            ("c", "2", lambda c: 2),
            ("d", "argc - 1", lambda c: c["argc"] - 1),
        )),
    },
    ref={"depart": "a"},
    rows=_somme_rows,
    level=2,
)


# --------------------------------------------------------------------------
# Le plus grand argument
# --------------------------------------------------------------------------

def _max_rows(p, get):
    args = p["args"]
    test = get("cond")
    maxi, out = args[0], []
    for v in args[1:]:
        if test({"v": v, "maxi": maxi}):
            maxi = v
        out.append(str(maxi))
    return out + ["max %d" % maxi]


MAXIMUM = Pattern(
    key="arg_max",
    name="Le plus grand argument",
    brief="Trouver la plus grande valeur parmi les arguments.",
    why="La référence de départ vient des données, pas d'une constante.",
    lesson=(
        "On initialise avec le **premier argument**, `argv[1]`, et la "
        "boucle démarre au deuxième.",
        "Partir de 0 casserait tout si tous les arguments étaient négatifs.",
        "À chaque tour, on remplace la référence si la valeur courante "
        "est plus grande.",
    ),
    dims=(("n", 4, 6), ("g", 0, 3)),
    derive=_jeu,
    tpl="""/* Lancé par :  ./programme @ligne@ */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    int maxi = atoi(argv[1]);
    for (int i = 2; i < argc; i++) {
        int v = atoi(argv[i]);
        if (@cond@) {
            maxi = v;
        }
        printf("%d\\n", maxi);
    }
    printf("max %d\\n", maxi);
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "v > maxi", lambda c: c["v"] > c["maxi"]),
            ("b", "v < maxi", lambda c: c["v"] < c["maxi"]),
            ("c", "v != maxi", lambda c: c["v"] != c["maxi"]),
            ("d", "v > 0", lambda c: c["v"] > 0),
        )),
    },
    ref={"cond": "a"},
    rows=_max_rows,
    level=2,
)


# --------------------------------------------------------------------------
# Le plus proche de zéro
# --------------------------------------------------------------------------

def _proche_rows(p, get):
    args = p["args"]
    test = get("cond")
    ref, retenu, out = abs(args[0]), args[0], []
    for v in args[1:]:
        if test({"v": v, "ref": ref}):
            ref, retenu = abs(v), v
        out.append(str(retenu))
    return out + ["retenu %d" % retenu]


PROCHE_ZERO = Pattern(
    key="arg_proche_zero",
    name="L'argument le plus proche de zéro",
    brief="Trouver la valeur la plus proche de 0. À égalité, le positif gagne.",
    why="Deux critères, donc deux conditions reliées par un ou.",
    lesson=(
        "La distance à zéro est la **valeur absolue** : `abs(-3)` vaut 3.",
        "Les arguments contiennent une paire comme -1 et 1 : à distance "
        "égale, l'énoncé demande de garder le positif.",
        "Le second critère ne s'applique qu'en cas d'égalité : d'où le "
        "`||` et le `==` qui l'accompagne.",
    ),
    dims=(("n", 4, 6), ("g", 0, 3)),
    derive=_jeu,
    tpl="""/* Lancé par :  ./programme @ligne@ */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    int ref = abs(atoi(argv[1]));
    int retenu = atoi(argv[1]);
    for (int i = 2; i < argc; i++) {
        int v = atoi(argv[i]);
        if (@cond@) {
            ref = abs(v);
            retenu = v;
        }
        printf("%d\\n", retenu);
    }
    printf("retenu %d\\n", retenu);
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "abs(v) < ref || (abs(v) == ref && v > 0)",
             lambda c: abs(c["v"]) < c["ref"]
             or (abs(c["v"]) == c["ref"] and c["v"] > 0)),
            ("b", "abs(v) < ref", lambda c: abs(c["v"]) < c["ref"]),
            ("c", "v < ref", lambda c: c["v"] < c["ref"]),
            ("d", "abs(v) > ref", lambda c: abs(c["v"]) > c["ref"]),
        )),
    },
    ref={"cond": "a"},
    rows=_proche_rows,
    level=3,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

BUG_ARGV0 = debug_pattern(
    key="bug_argv0",
    name="Bug : la moyenne des arguments",
    but="afficher la moyenne des nombres passés en ligne de commande",
    defaut="boucle démarrée à 0 : le nom du programme compte pour une valeur",
    dims=(("n", 4, 6), ("g", 0, 3)),
    derive=_jeu_moyenne,
    tpl="""/* Lancé par :  ./programme @ligne@ */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    int somme = 0;
    for (int i = 0; i < argc; i++) {
        somme = somme + atoi(argv[i]);
    }
    printf("%d\\n", somme / argc);
    return 0;
}""",
    attendu=lambda p: [str(int(sum(p["args"]) / len(p["args"])))],
    obtenu=lambda p: [str(int(sum(p["args"]) / (len(p["args"]) + 1)))],
    diagnostics=(
        ("a", "La boucle démarre à 0 et divise par `argc` : le nom du "
              "programme est compté comme une valeur de plus.",
         "Exact. `atoi(argv[0])` rend 0, donc la somme est juste — mais on "
         "divise par un nombre trop grand d'une unité. Il faut boucler de 1 "
         "à `argc - 1` et diviser par `argc - 1`."),
        ("b", "`atoi` ne sait pas lire les nombres négatifs.",
         "Non : `atoi(\"-3\")` rend bien -3. La somme est correcte, c'est "
         "le diviseur qui ne l'est pas."),
        ("c", "Il manque un `return` dans la boucle.",
         "Non : la boucle doit parcourir tous les arguments. Un `return` "
         "l'interromprait au premier tour."),
        ("d", "La division entière tronque le résultat.",
         "Elle tronque, c'est vrai, mais l'écart observé ne vient pas de "
         "là : recomptez combien de valeurs sont réellement additionnées."),
    ),
    bonne="a",
    level=2,
)


PREDIRE_SOMME = predict_from(
    SOMME,
    key="predire_arg_somme",
    name="Prédire : la somme des arguments",
    why="Suivre un accumulateur qui s'affiche à chaque tour.",
    level=2,
    output_format=(
        "TOTAL",
        "TOTAL",
        "…",
        "total TOTAL",
    ),
    dims=(("n", 3, 5), ("g", 0, 3)),
)


PATTERNS = (CARRE, COMBIEN, SOMME, MAXIMUM, PROCHE_ZERO,
            BUG_ARGV0, PREDIRE_SOMME)

MODULE = Module(
    key="arguments",
    title="Les arguments de la ligne de commande",
    level=2,
    summary="argc, argv et atoi : lire ce que l'utilisateur passe au "
            "programme, sans oublier que argv[0] est le programme lui-même.",
    keys=tuple(p.key for p in PATTERNS),
)
