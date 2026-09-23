"""Module « Les chaînes de caractères » : parcours, indices, comparaisons.

Les phrases sont volontairement sans accent : en C une chaîne est un
tableau d'octets, et `printf("%c", …)` afficherait un demi-caractère UTF-8.
Les exercices restent donc sur de l'ASCII, ce qui est aussi la réalité du
`char` du langage.
"""

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from

PHRASES = (
    "l'hiver sera pluvieux",
    "le vent se leve encore",
    "les etoiles reviennent",
    "chercher et esperer",
)

LETTRES = "eras"

# Trois palindromes et trois faux. Chaque faux a au moins une paire qui
# coïncide : sans cela, une condition toujours vraie donnerait exactement
# la même sortie que la bonne réponse, et serait acceptée à tort.
MOTS = ("radar", "kayak", "ressasser", "revoir", "renier", "salades")


def _at(s, i):
    """Caractère d'indice i, '\\0' au-delà de la fin — comme en C."""
    return s[i] if 0 <= i < len(s) else "\0"


def _phrase(p):
    return {"phrase": PHRASES[p["k"]]}


def _phrase_lettre(p):
    return {"phrase": PHRASES[p["k"]], "lettre": LETTRES[p["l"]]}


def _mot(p):
    return {"mot": MOTS[p["k"]]}


# --------------------------------------------------------------------------
# La longueur
# --------------------------------------------------------------------------

def _longueur_rows(p, get):
    s, test, n = p["phrase"], get("cond"), 0
    while n < 200 and test({"s": s, "n": n}):
        n += 1
    return [str(n)]


LONGUEUR = Pattern(
    key="str_longueur",
    name="La longueur d'une chaîne",
    brief="Compter les caractères d'une phrase, sans strlen.",
    why="Une chaîne C se termine par un octet nul. Tout part de là.",
    lesson=(
        "En C, une chaîne est un tableau de `char` terminé par `'\\0'`.",
        "Ce caractère invisible n'est pas compté dans la longueur : il la "
        "**marque**.",
        "Parcourir une chaîne, c'est avancer jusqu'à le rencontrer.",
    ),
    dims=(("k", 0, len(PHRASES) - 1),),
    derive=_phrase,
    tpl="""#include <stdio.h>

int main(void) {
    char s[] = "@phrase@";
    int n = 0;
    while (@cond@) {
        n++;
    }
    printf("%d\\n", n);
    return 0;
}""",
    blanks={
        "cond": ("Condition du while", _opts(
            ("a", "s[n] != '\\0'", lambda c: _at(c["s"], c["n"]) != "\0"),
            ("b", "s[n] == '\\0'", lambda c: _at(c["s"], c["n"]) == "\0"),
            ("c", "s[n] != ' '", lambda c: _at(c["s"], c["n"]) != " "),
            ("d", "n < 5", lambda c: c["n"] < 5),
        )),
    },
    ref={"cond": "a"},
    rows=_longueur_rows,
    level=1,
)


# --------------------------------------------------------------------------
# Compter une lettre
# --------------------------------------------------------------------------

def _compter_rows(p, get):
    # On affiche les positions et pas seulement le total : deux conditions
    # différentes peuvent compter autant de fois sans trouver aux mêmes
    # endroits, et l'élève verrait alors juste avec une réponse fausse.
    s, cible, test = p["phrase"], p["lettre"], get("cond")
    out = [str(i) for i in range(len(s))
           if test({"s": s, "i": i, "cible": cible})]
    return out + ["total %d" % len(out)]


COMPTER = Pattern(
    key="str_compter",
    name="Compter une lettre",
    brief="Combien de fois une lettre donnée apparaît dans la phrase ?",
    why="Un parcours, un test, un compteur. Le trio de base.",
    lesson=(
        "`s[i]` est le caractère d'indice `i`. Le premier a l'indice 0.",
        "Un `char` se compare avec `==`, et s'écrit entre apostrophes "
        "simples : `'e'`, pas `\"e\"`.",
        "`\"e\"` serait une chaîne de deux octets : la lettre et son `'\\0'`.",
    ),
    dims=(("k", 0, len(PHRASES) - 1), ("l", 0, len(LETTRES) - 1)),
    derive=_phrase_lettre,
    tpl="""#include <stdio.h>

int main(void) {
    char s[] = "@phrase@";
    char cible = '@lettre@';
    int cpt = 0;
    for (int i = 0; s[i] != '\\0'; i++) {
        if (@cond@) {
            printf("%d\\n", i);
            cpt++;
        }
    }
    printf("total %d\\n", cpt);
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "s[i] == cible", lambda c: _at(c["s"], c["i"]) == c["cible"]),
            ("b", "s[i] != cible", lambda c: _at(c["s"], c["i"]) != c["cible"]),
            ("c", "s[i] == ' '", lambda c: _at(c["s"], c["i"]) == " "),
            ("d", "s[i] > cible", lambda c: _at(c["s"], c["i"]) > c["cible"]),
        )),
    },
    ref={"cond": "a"},
    rows=_compter_rows,
    level=2,
)


# --------------------------------------------------------------------------
# Un mot par ligne
# --------------------------------------------------------------------------

def _lignes_rows(p, get):
    s, test = p["phrase"], get("cond")
    out, courant = [], ""
    for i in range(len(s)):
        if test({"s": s, "i": i}):
            out.append(courant)
            courant = ""
        else:
            courant += s[i]
    out.append(courant)
    return out


LIGNES = Pattern(
    key="str_lignes",
    name="Un mot par ligne",
    brief="Réafficher la phrase en passant à la ligne à chaque espace.",
    why="L'espace est un caractère comme un autre : il se teste.",
    lesson=(
        "L'espace s'écrit `' '` : c'est un caractère, pas une absence.",
        "`printf(\"%c\", s[i])` affiche un caractère sans passer à la ligne.",
        "Il suffit donc de choisir, à chaque tour, entre l'afficher et "
        "passer à la ligne.",
    ),
    dims=(("k", 0, len(PHRASES) - 1),),
    derive=_phrase,
    tpl="""#include <stdio.h>

int main(void) {
    char s[] = "@phrase@";
    for (int i = 0; s[i] != '\\0'; i++) {
        if (@cond@) {
            printf("\\n");
        } else {
            printf("%c", s[i]);
        }
    }
    printf("\\n");
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "s[i] == ' '", lambda c: _at(c["s"], c["i"]) == " "),
            ("b", "s[i] != ' '", lambda c: _at(c["s"], c["i"]) != " "),
            ("c", "s[i] == 'e'", lambda c: _at(c["s"], c["i"]) == "e"),
            ("d", "i % 5 == 0", lambda c: c["i"] % 5 == 0),
        )),
    },
    ref={"cond": "a"},
    rows=_lignes_rows,
    level=2,
)


# --------------------------------------------------------------------------
# À l'envers
# --------------------------------------------------------------------------

def _envers_rows(p, get):
    s, test = p["phrase"], get("cond")
    n, sortie, i = len(s), "", len(s) - 1
    garde = 0
    while test({"i": i, "n": n}) and garde < 300:
        sortie += _at(s, i)
        i -= 1
        garde += 1
    return [sortie]


ENVERS = Pattern(
    key="str_envers",
    name="À l'envers",
    brief="Réafficher la phrase du dernier caractère au premier.",
    why="Parcourir en sens inverse demande de savoir où s'arrêter.",
    lesson=(
        "Le dernier caractère utile est à l'indice `n - 1`, pas `n` : "
        "`s[n]` est le `'\\0'`.",
        "En descendant, la boucle s'arrête quand l'indice devient négatif.",
        "Oublier l'indice 0, c'est perdre la première lettre.",
    ),
    dims=(("k", 0, len(PHRASES) - 1),),
    derive=_phrase,
    tpl="""#include <stdio.h>

int main(void) {
    char s[] = "@phrase@";
    int n = 0;
    while (s[n] != '\\0') {
        n++;
    }
    for (int i = n - 1; @cond@; i--) {
        printf("%c", s[i]);
    }
    printf("\\n");
    return 0;
}""",
    blanks={
        "cond": ("Condition de la boucle", _opts(
            ("a", "i >= 0", lambda c: c["i"] >= 0),
            ("b", "i > 0", lambda c: c["i"] > 0),
            ("c", "i >= n / 2", lambda c: c["i"] >= c["n"] // 2),
            ("d", "i != 0", lambda c: c["i"] != 0),
        )),
    },
    ref={"cond": "a"},
    rows=_envers_rows,
    level=2,
)


# --------------------------------------------------------------------------
# Palindrome
# --------------------------------------------------------------------------

def _palindrome_rows(p, get):
    mot, test = p["mot"], get("cond")
    n = len(mot)
    out, ok = [], True
    for i in range(n // 2):
        if test({"s": mot, "i": i, "n": n}):
            out.append("%s et %s different" % (_at(mot, i), _at(mot, n - 1 - i)))
            ok = False
    out.append("palindrome" if ok else "pas palindrome")
    return out


PALINDROME = Pattern(
    key="str_palindrome",
    name="Le palindrome",
    brief="Un mot se lit-il pareil dans les deux sens ?",
    why="Comparer le début et la fin, en avançant par les deux bouts.",
    lesson=(
        "Le caractère d'indice `i` a pour symétrique celui d'indice "
        "`n - 1 - i`.",
        "Il suffit de parcourir la première moitié : au-delà, on "
        "recomparerait les mêmes paires.",
        "Une seule paire différente suffit à disqualifier le mot.",
    ),
    dims=(("k", 0, len(MOTS) - 1),),
    derive=_mot,
    tpl="""#include <stdio.h>

int main(void) {
    char s[] = "@mot@";
    int n = 0;
    while (s[n] != '\\0') {
        n++;
    }
    int ok = 1;
    for (int i = 0; i < n / 2; i++) {
        if (@cond@) {
            printf("%c et %c different\\n", s[i], s[n - 1 - i]);
            ok = 0;
        }
    }
    if (ok) {
        printf("palindrome\\n");
    } else {
        printf("pas palindrome\\n");
    }
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "s[i] != s[n - 1 - i]",
             lambda c: _at(c["s"], c["i"]) != _at(c["s"], c["n"] - 1 - c["i"])),
            ("b", "s[i] == s[n - 1 - i]",
             lambda c: _at(c["s"], c["i"]) == _at(c["s"], c["n"] - 1 - c["i"])),
            ("c", "s[i] != s[n - i]",
             lambda c: _at(c["s"], c["i"]) != _at(c["s"], c["n"] - c["i"])),
            ("d", "s[i] != s[i + 1]",
             lambda c: _at(c["s"], c["i"]) != _at(c["s"], c["i"] + 1)),
        )),
    },
    ref={"cond": "a"},
    rows=_palindrome_rows,
    level=3,
)


# --------------------------------------------------------------------------
# Compter un groupe de deux lettres
# --------------------------------------------------------------------------

def _occurrences_rows(p, get):
    s, test = p["phrase"], get("cond")
    out = [str(i) for i in range(max(0, len(s) - 1))
           if test({"s": s, "i": i})]
    return out + ["total %d" % len(out)]


OCCURRENCES = Pattern(
    key="str_occurrences",
    name="Compter les « er »",
    brief="Combien de fois le groupe « er » apparaît dans la phrase ?",
    why="Un motif de deux caractères demande de regarder l'indice suivant.",
    lesson=(
        "Chercher deux caractères de suite, c'est tester `s[i]` **et** "
        "`s[i + 1]` au même tour.",
        "La boucle doit s'arrêter un cran plus tôt : sinon `s[i + 1]` "
        "dépasse la fin.",
        "`&&` et non `||` : les deux lettres doivent y être, dans l'ordre.",
    ),
    dims=(("k", 0, len(PHRASES) - 1),),
    derive=_phrase,
    tpl="""#include <stdio.h>

int main(void) {
    char s[] = "@phrase@";
    int cpt = 0;
    for (int i = 0; s[i] != '\\0' && s[i + 1] != '\\0'; i++) {
        if (@cond@) {
            printf("%d\\n", i);
            cpt++;
        }
    }
    printf("total %d\\n", cpt);
    return 0;
}""",
    blanks={
        "cond": ("Condition du if", _opts(
            ("a", "s[i] == 'e' && s[i + 1] == 'r'",
             lambda c: _at(c["s"], c["i"]) == "e"
             and _at(c["s"], c["i"] + 1) == "r"),
            ("b", "s[i] == 'e' || s[i + 1] == 'r'",
             lambda c: _at(c["s"], c["i"]) == "e"
             or _at(c["s"], c["i"] + 1) == "r"),
            ("c", "s[i] == 'r' && s[i + 1] == 'e'",
             lambda c: _at(c["s"], c["i"]) == "r"
             and _at(c["s"], c["i"] + 1) == "e"),
            ("d", "s[i] == 'e'", lambda c: _at(c["s"], c["i"]) == "e"),
        )),
    },
    ref={"cond": "a"},
    rows=_occurrences_rows,
    level=3,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

BUG_PREMIER = debug_pattern(
    key="bug_premier_caractere",
    name="Bug : la phrase recopiée",
    but="réafficher la phrase caractère par caractère",
    defaut="la boucle démarre à 1 : le premier caractère est sauté",
    dims=(("k", 0, len(PHRASES) - 1),),
    derive=_phrase,
    tpl="""#include <stdio.h>

int main(void) {
    char s[] = "@phrase@";
    for (int i = 1; s[i] != '\\0'; i++) {
        printf("%c", s[i]);
    }
    printf("\\n");
    return 0;
}""",
    attendu=lambda p: [p["phrase"]],
    obtenu=lambda p: [p["phrase"][1:]],
    diagnostics=(
        ("a", "La boucle démarre à l'indice 1. Or le premier caractère "
              "d'une chaîne est à l'indice 0.",
         "Exact. En C, l'indexation commence à 0 : `s[0]` est la première "
         "lettre. Partir de 1 la saute, et une seule."),
        ("b", "La condition d'arrêt est fausse : il manque un caractère "
              "à la fin.",
         "Non : comparez le dernier caractère affiché avec celui de la "
         "phrase attendue. C'est au **début** que quelque chose manque."),
        ("c", "Il faut `%s` et non `%c` dans le `printf`.",
         "Non : afficher caractère par caractère est justement l'exercice, "
         "et `%c` est le bon format pour cela."),
        ("d", "Le `printf(\"\\\\n\")` final est en trop.",
         "Non : la sortie attendue tient aussi sur une ligne. Le nombre de "
         "lignes est bon, c'est leur contenu qui est amputé."),
    ),
    bonne="a",
    level=2,
)


PREDIRE_ENVERS = predict_from(
    ENVERS,
    key="predire_envers",
    name="Prédire : la phrase à l'envers",
    why="Lire une chaîne à rebours sans l'écrire, juste en la parcourant.",
    level=3,
    output_format=("<une seule ligne de texte>",),
)


PATTERNS = (LONGUEUR, COMPTER, LIGNES, ENVERS, PALINDROME, OCCURRENCES,
            BUG_PREMIER, PREDIRE_ENVERS)

MODULE = Module(
    key="chaines",
    title="Les chaînes de caractères",
    level=2,
    summary="Une chaîne est un tableau de char terminé par '\\0' : "
            "parcours, indices, comparaisons de caractères.",
    keys=tuple(p.key for p in PATTERNS),
)
