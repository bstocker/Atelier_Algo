"""Module « Itératif et récursif » : une fonction qui s'appelle elle-même."""

from ..engine import InfiniteLoop, Module, Pattern, _opts, debug_pattern, predict_from

CAP = 200   # au-delà, on considère que la récursion ne s'arrête pas


def _descend(depart, base, suivant, action):
    """Déroule une récursion. Lève InfiniteLoop si elle ne s'arrête pas.

    C'est l'équivalent récursif de la boucle infinie : sans cas d'arrêt
    atteignable, le programme empile des appels jusqu'au débordement.
    """
    n, out = depart, []
    for _ in range(CAP):
        if base(n):
            return out, n
        action(out, n)
        n = suivant(n)
    raise InfiniteLoop()


# --------------------------------------------------------------------------
# Le compteur récursif
# --------------------------------------------------------------------------

def _compteur_rows(p, get):
    base, suivant = get("base"), get("suivant")
    out, final = _descend(
        p["n"],
        lambda n: base({"n": n}),
        lambda n: suivant({"n": n}),
        lambda acc, n: acc.append("n = %d" % n),
    )
    return out + ["resultat %d" % final]


COMPTEUR = Pattern(
    key="rec_compteur",
    name="Le compteur récursif",
    brief="Compter jusqu'à 5 sans boucle, en rappelant la fonction.",
    why="Une récursion, c'est un cas d'arrêt et un pas vers lui.",
    lesson=(
        "Une fonction récursive s'appelle elle-même. Elle a besoin de deux "
        "choses : un **cas d'arrêt**, et un pas qui s'en rapproche.",
        "Le cas d'arrêt se teste **avant** de rappeler la fonction, sinon "
        "l'appel a lieu de toute façon.",
        "Si le pas éloigne du cas d'arrêt, les appels s'empilent jusqu'au "
        "débordement de pile — l'équivalent récursif de la boucle infinie.",
    ),
    dim=("n", 0, 3),
    tpl="""#include <stdio.h>

int compte(int n) {
    if (n == 5) {
        return n;
    }
    printf("n = %d\\n", n);
    return compte(@suivant@);
}

int main(void) {
    printf("resultat %d\\n", compte(@n@));
    return 0;
}""",
    blanks={
        "base": ("Cas d'arrêt (déjà écrit)", _opts(
            ("a", "n == 5", lambda c: c["n"] == 5),
        )),
        "suivant": ("Argument de l'appel récursif", _opts(
            ("a", "n + 1", lambda c: c["n"] + 1),
            ("b", "n - 1", lambda c: c["n"] - 1),
            ("c", "n + 2", lambda c: c["n"] + 2),
            ("d", "n", lambda c: c["n"]),
        )),
    },
    ref={"base": "a", "suivant": "a"},
    rows=_compteur_rows,
    level=2,
)


# --------------------------------------------------------------------------
# La ligne d'étoiles, en récursif
# --------------------------------------------------------------------------

def _ligne_rows(p, get):
    base, suivant = get("base"), get("suivant")
    out, _final = _descend(
        p["n"],
        lambda n: base({"n": n}),
        lambda n: suivant({"n": n}),
        lambda acc, n: acc.append("*"),
    )
    return ["".join(out)]


LIGNE_REC = Pattern(
    key="rec_ligne",
    name="La ligne d'étoiles, en récursif",
    brief="Afficher n étoiles sans aucune boucle.",
    why="Ce qu'une boucle répète, une récursion le délègue à l'appel suivant.",
    lesson=(
        "Chaque appel affiche **une** étoile, puis confie le reste au "
        "suivant.",
        "Le cas d'arrêt joue le rôle de la condition de boucle : il dit "
        "quand ne plus rien afficher.",
        "Le pas joue le rôle de l'incrément. Ici il faut descendre vers "
        "le cas d'arrêt, pas s'en éloigner.",
    ),
    dim=("n", 3, 7),
    tpl="""#include <stdio.h>

void ligne(int n) {
    if (@base@) {
        return;
    }
    printf("*");
    ligne(@suivant@);
}

int main(void) {
    ligne(@n@);
    printf("\\n");
    return 0;
}""",
    blanks={
        "base": ("Cas d'arrêt", _opts(
            ("a", "n == 0", lambda c: c["n"] == 0),
            ("b", "n == 1", lambda c: c["n"] == 1),
            ("c", "n < 0", lambda c: c["n"] < 0),
            ("d", "n > 0", lambda c: c["n"] > 0),
        )),
        "suivant": ("Argument de l'appel récursif", _opts(
            ("a", "n - 1", lambda c: c["n"] - 1),
            ("b", "n", lambda c: c["n"]),
            ("c", "n + 1", lambda c: c["n"] + 1),
            ("d", "n - 2", lambda c: c["n"] - 2),
        )),
    },
    ref={"base": "a", "suivant": "a"},
    rows=_ligne_rows,
    level=2,
)


# --------------------------------------------------------------------------
# La table de multiplication, en récursif
# --------------------------------------------------------------------------

def _table_rows(p, get):
    v = p["v"]
    base, suivant = get("base"), get("suivant")
    out, _final = _descend(
        1,
        lambda m: base({"m": m}),
        lambda m: suivant({"m": m}),
        lambda acc, m: acc.append("%d x %d = %d" % (v, m, v * m)),
    )
    return out or [""]


TABLE_REC = Pattern(
    key="rec_table",
    name="La table de multiplication, en récursif",
    brief="Afficher la table de v, de 1 à 10, sans boucle.",
    why="Deux paramètres : l'un porte la donnée, l'autre l'avancement.",
    lesson=(
        "Une récursion peut transporter plusieurs valeurs : ici `v` ne "
        "change jamais, `m` avance à chaque appel.",
        "Le cas d'arrêt porte sur `m`, pas sur `v`.",
        "Pour aller de 1 à 10, il faut s'arrêter **après** 10, donc "
        "tester au-delà.",
    ),
    value=("v", 2, 9),
    tpl="""#include <stdio.h>

void table(int v, int m) {
    if (@base@) {
        return;
    }
    printf("%d x %d = %d\\n", v, m, v * m);
    table(v, @suivant@);
}

int main(void) {
    int v;
    scanf("%d", &v);          /* l'utilisateur a saisi @v@ */
    table(v, 1);
    return 0;
}""",
    blanks={
        "base": ("Cas d'arrêt", _opts(
            ("a", "m > 10", lambda c: c["m"] > 10),
            ("b", "m > 9", lambda c: c["m"] > 9),
            ("c", "m == 1", lambda c: c["m"] == 1),
            ("d", "m > 11", lambda c: c["m"] > 11),
        )),
        "suivant": ("Argument de l'appel récursif", _opts(
            ("a", "m + 1", lambda c: c["m"] + 1),
            ("b", "m", lambda c: c["m"]),
            ("c", "m + 2", lambda c: c["m"] + 2),
            ("d", "m - 1", lambda c: c["m"] - 1),
        )),
    },
    ref={"base": "a", "suivant": "a"},
    rows=_table_rows,
    level=3,
)


# --------------------------------------------------------------------------
# La somme, en récursif
# --------------------------------------------------------------------------

def _somme_rows(p, get):
    expr = get("expr")
    memo = {}

    def somme(n, profondeur=0):
        if profondeur > CAP:
            raise InfiniteLoop()
        if n == 0:
            return 0
        if n not in memo:
            memo[n] = expr({"n": n, "somme": lambda k: somme(k, profondeur + 1)})
        return memo[n]

    return ["somme %d" % somme(p["n"])]


SOMME_REC = Pattern(
    key="rec_somme",
    name="La somme de 1 à n, en récursif",
    brief="Additionner les entiers de 1 à n sans accumulateur ni boucle.",
    why="Le résultat d'un appel se combine avec celui de l'appel suivant.",
    lesson=(
        "La somme de 1 à n vaut n **plus** la somme de 1 à n-1.",
        "C'est la définition récursive : le problème se ramène au même "
        "problème, en plus petit.",
        "Le cas d'arrêt donne la valeur neutre : la somme de 1 à 0 vaut 0.",
    ),
    dim=("n", 3, 8),
    tpl="""#include <stdio.h>

int somme(int n) {
    if (n == 0) {
        return 0;
    }
    return @expr@;
}

int main(void) {
    printf("somme %d\\n", somme(@n@));
    return 0;
}""",
    blanks={
        "expr": ("Valeur rendue", _opts(
            ("a", "n + somme(n - 1)", lambda c: c["n"] + c["somme"](c["n"] - 1)),
            ("b", "somme(n - 1)", lambda c: c["somme"](c["n"] - 1)),
            ("c", "n * somme(n - 1)", lambda c: c["n"] * c["somme"](c["n"] - 1)),
            ("d", "n + somme(n)", lambda c: c["n"] + c["somme"](c["n"])),
        )),
    },
    ref={"expr": "a"},
    rows=_somme_rows,
    level=3,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

BUG_SANS_ARRET = debug_pattern(
    key="bug_sans_arret",
    name="Bug : la ligne d'étoiles récursive",
    but="afficher n étoiles au moyen d'une fonction récursive",
    defaut="aucun cas d'arrêt : la récursion ne se termine jamais",
    dim=("n", 3, 7),
    tpl="""#include <stdio.h>

void ligne(int n) {
    printf("*");
    ligne(n - 1);
}

int main(void) {
    ligne(@n@);
    printf("\\n");
    return 0;
}""",
    attendu=lambda p: ["*" * p["n"]],
    obtenu=lambda p: ["**** … (le programme s'arrête : débordement de pile)"],
    diagnostics=(
        ("a", "La fonction n'a pas de cas d'arrêt : elle se rappelle "
              "toujours, même avec un `n` négatif.",
         "Exact. Sans `if` qui arrête la descente, chaque appel en déclenche "
         "un autre. La pile d'appels finit par déborder, et le système "
         "arrête le programme."),
        ("b", "Le pas est faux : il faudrait `ligne(n + 1)`.",
         "Non : ce serait pire encore. Le pas descend bien, mais rien "
         "ne dit quand s'arrêter de descendre."),
        ("c", "Il manque un `return` à la fin de la fonction.",
         "Non : la fonction ne rend rien, `void` est correct. Le problème "
         "est qu'elle ne s'arrête pas."),
        ("d", "`printf` devrait être après l'appel récursif.",
         "Non : l'ordre changerait celui des étoiles, pas le fait qu'il y "
         "en ait une infinité."),
    ),
    bonne="a",
    level=3,
)


PREDIRE_TABLE = predict_from(
    TABLE_REC,
    key="predire_table_rec",
    name="Prédire : la table récursive",
    why="Suivre une récursion à deux paramètres jusqu'à son cas d'arrêt.",
    level=3,
    output_format=(
        "V x M = R",
        "V x M = R",
        "…",
    ),
)


PATTERNS = (COMPTEUR, LIGNE_REC, TABLE_REC, SOMME_REC,
            BUG_SANS_ARRET, PREDIRE_TABLE)

MODULE = Module(
    key="recursif",
    title="Itératif et récursif",
    level=3,
    summary="Une fonction qui s'appelle elle-même : cas d'arrêt, pas, "
            "et ce qui arrive quand l'un des deux manque.",
    keys=tuple(p.key for p in PATTERNS),
)
