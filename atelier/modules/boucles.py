"""Module « Les boucles » : de la boucle simple aux motifs imbriqués."""

from ..engine import (Module, Pattern, _diag, _opts, _never_ends,
                      condition_trace, debug_pattern, predict_from,
                      step_trace)


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



BUG_BORNE = debug_pattern(
    key="bug_borne",
    name="Bug : le triangle rectangle",
    but="dessiner un triangle rectangle de n lignes",
    defaut="borne exclue, j < i au lieu de j <= i",
    dim=("n", 4, 7),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < i; j++) {
            printf("*");
        }
        printf("\\n");
    }
    return 0;
}""",
    attendu=lambda p: ["*" * (i + 1) for i in range(p["n"])],
    obtenu=lambda p: ["*" * i for i in range(p["n"])],
    diagnostics=(
        ("a", "La boucle des étoiles s'arrête un tour trop tôt : "
              "`j < i` exclut la valeur `i`.",
         "Exact. Pour la ligne i, il faut i+1 étoiles, donc `j <= i` "
         "ou `j < i + 1`. La première ligne vide est le signe le plus net."),
        ("b", "La boucle des lignes s'arrête un tour trop tôt.",
         "Non : le nombre de lignes est bon. C'est leur contenu qui est "
         "décalé, ligne après ligne."),
        ("c", "Le `printf(\"\\n\")` est mal placé.",
         "Non : chaque ligne est bien terminée, le motif a le bon nombre "
         "de lignes. Le problème est le nombre d'étoiles."),
        ("d", "Le compteur `i` devrait partir de 1.",
         "Tentant, mais alors la boucle ferait une ligne de moins. "
         "Regardez plutôt la condition de la boucle interne."),
    ),
    bonne="a",
    level=2,
)


BUG_INVERSE = debug_pattern(
    key="bug_inverse",
    name="Bug : la ligne d'étoiles",
    but="afficher une ligne de n étoiles",
    defaut="comparaison inversée, la boucle ne démarre jamais",
    dim=("n", 4, 8),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int j = 0; j > n; j++) {
        printf("*");
    }
    printf("\\n");
    return 0;
}""",
    attendu=lambda p: ["*" * p["n"]],
    obtenu=lambda p: [""],
    diagnostics=(
        ("a", "La comparaison est dans le mauvais sens : `j > n` est faux "
              "dès le premier test, la boucle ne s'exécute jamais.",
         "Exact. Le test est évalué avant le premier tour : `0 > n` est faux, "
         "le corps n'est jamais atteint. D'où une ligne vide."),
        ("b", "Il manque le `printf(\"\\n\")` à la fin.",
         "Non : il est bien là, et c'est même lui qui produit la ligne vide "
         "que vous observez."),
        ("c", "`j` devrait partir de `n` au lieu de 0.",
         "Non : avec `j = n`, le test `j > n` serait encore faux. "
         "Le sens de la comparaison est en cause, pas le départ."),
        ("d", "La boucle s'arrête un tour trop tôt.",
         "Non : elle ne s'exécute pas du tout. Aucune étoile n'est imprimée, "
         "pas même une."),
    ),
    bonne="a",
    level=2,
)


BUG_ACCOLADES = debug_pattern(
    key="bug_accolades",
    name="Bug : les n lignes",
    but="afficher n lignes d'une étoile chacune",
    defaut="accolades manquantes, l'indentation trompe le lecteur",
    dim=("n", 3, 6),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    for (int i = 0; i < n; i++)
        printf("*");
        printf("\\n");
    return 0;
}""",
    attendu=lambda p: ["*"] * p["n"],
    obtenu=lambda p: ["*" * p["n"]],
    diagnostics=(
        ("a", "Sans accolades, la boucle ne répète que la première "
              "instruction : le retour à la ligne est hors de la boucle.",
         "Exact. L'indentation suggère deux instructions dans la boucle, "
         "mais le compilateur n'en voit qu'une. Les n étoiles sortent donc "
         "d'affilée, suivies d'un seul retour à la ligne."),
        ("b", "Il manque un `\\n` dans le premier `printf`.",
         "Non : l'ajouter donnerait le bon résultat par accident, mais "
         "la cause reste que le second printf n'est pas dans la boucle."),
        ("c", "La condition devrait être `i <= n`.",
         "Non : le nombre d'étoiles est correct. C'est leur répartition "
         "en lignes qui ne l'est pas."),
        ("d", "Les deux `printf` sont dans le mauvais ordre.",
         "Non : les inverser donnerait un retour à la ligne avant les "
         "étoiles, pas n lignes d'une étoile."),
    ),
    bonne="a",
    level=3,
)


BUG_REINIT = debug_pattern(
    key="bug_reinit",
    name="Bug : la somme de 1 à n",
    but="calculer la somme des entiers de 1 à n",
    defaut="accumulateur remis à zéro dans la boucle",
    dim=("n", 4, 9),
    tpl="""#include <stdio.h>

int main(void) {
    int n = @n@;
    int total = 0;
    for (int i = 1; i <= n; i++) {
        total = 0;
        total = total + i;
    }
    printf("%d\\n", total);
    return 0;
}""",
    attendu=lambda p: [str(sum(range(1, p["n"] + 1)))],
    obtenu=lambda p: [str(p["n"])],
    diagnostics=(
        ("a", "`total` est remis à zéro **dans** la boucle : seul le dernier "
              "tour subsiste.",
         "Exact. L'initialisation doit rester avant la boucle. Ici elle est "
         "répétée à chaque tour, d'où le résultat égal au dernier `i`."),
        ("b", "La boucle devrait commencer à 0.",
         "Non : ajouter 0 ne changerait rien à la somme. Et le résultat "
         "obtenu vaut n, pas une somme incomplète."),
        ("c", "Le `printf` devrait être dans la boucle.",
         "Non : on veut une seule valeur à la fin. Le déplacer afficherait "
         "n lignes, toutes fausses de la même façon."),
        ("d", "Il manque un `total++` après l'addition.",
         "Non : l'addition elle-même est correcte. C'est ce qui la précède "
         "qui annule son effet."),
    ),
    bonne="a",
    level=3,
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


PATTERNS = (LIGNE, REBOURS, PAS, WHILE,
            CARRE, TRIANGLE_RECT, TRIANGLE_INV, TRIANGLE_DROITE,
            LOSANGE, PYRAMIDE, CARRE_MAGIQUE, TABLE,
            BUG_BORNE, BUG_INVERSE, BUG_ACCOLADES, BUG_REINIT,
            PREDIRE_TRIANGLE, PREDIRE_MAGIQUE)

MODULE = Module(
    key="boucles",
    title="Les boucles",
    level=1,
    summary="De la boucle simple aux motifs imbriqués : répétition, "
            "compteur, condition d'arrêt, pas et accumulateur.",
    keys=tuple(p.key for p in PATTERNS),
)
