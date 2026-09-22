"""Module « Le shell » : variables, enchaînements, boucles, sed et awk.

Le terminal n'est pas qu'un lanceur de commandes : c'est un langage. Il
a des variables, des tests, des boucles, et deux outils de traitement de
texte qui méritent à eux seuls un cours. De quoi écrire un script — et
de quoi comprendre pourquoi un script mal cité tombe en panne.
"""

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from
from .linux_commun import lecon, trier

ARGUMENTS = (
    ("alpha", "beta", "gamma", "delta"),
    ("lyon", "paris", "nice", "brest"),
    ("mars", "avril", "mai", "juin"),
    ("rouge", "vert", "bleu", "jaune"),
)

# Un rapport lisible, et des voisins pour que la liste change d'un élève
# à l'autre. Les noms cités par le menu, eux, restent fixes.
RAPPORTS = (
    (("ligne une", "ligne deux"), ("agenda.txt", "brouillon.md")),
    (("premier point", "second point"), ("budget.csv", "contrat.pdf")),
    (("entree en matiere", "conclusion"), ("annexe.txt", "devis.odt")),
    (("etat des lieux", "suite du dossier"), ("bilan.md", "courrier.txt")),
)

# Textes où « chat » revient deux fois sur la première ligne : sans cela,
# `s/chat/loup/` et `s/chat/loup/g` rendraient la même chose.
TEXTES = (
    ("animaux.txt", ("chat noir chat", "chien blanc", "chat gris")),
    ("refuge.txt", ("chat roux chat", "lapin tremblant", "chat tigre")),
    ("perdus.txt", ("chat perdu chat", "oiseau bleu", "chat trouve")),
    ("voisins.txt", ("chat maigre chat", "cheval brun", "chat vieux")),
)

# Trois colonnes : la deuxième n'est donc pas la dernière, et `$2` se
# distingue de `$NF`.
STOCKS = (
    ("stock.txt", ("pomme 3 rouge", "banane 5 jaune", "cerise 2 rouge")),
    ("caisses.txt", ("vis 12 acier", "clou 40 fer", "ecrou 8 laiton")),
    ("rayon.txt", ("cahier 6 grand", "stylo 24 bleu", "gomme 9 blanche")),
    ("atelier.txt", ("scie 2 bois", "pince 7 metal", "lime 4 mixte")),
)

# Un fichier à nom d'une seule lettre, un autre en .txt, un troisième en
# .md : de quoi distinguer `*`, `*.txt`, `?.txt` et `*.md`.
GLOBS = (
    ("a.txt", "bilan.txt", "notes.md"),
    ("b.txt", "compte.txt", "guide.md"),
    ("c.txt", "devis.txt", "lisezmoi.md"),
    ("d.txt", "export.txt", "plan.md"),
)

# Noms en deux mots : le découpage du shell en fera deux arguments.
NOMS_ESPACES = ("rapport final.txt", "note de frais.txt",
                "compte rendu.txt", "budget 2024.txt")


# --------------------------------------------------------------------------
# Les arguments d'un script
# --------------------------------------------------------------------------

def _arguments(p):
    args = list(ARGUMENTS[p["g"]][:p["n"]])
    return {"args": args, "ligne": " ".join(args)}


ARGS = Pattern(
    key="lx_args",
    name="Les arguments d'un script",
    brief="Afficher le nombre d'arguments que le script a reçus.",
    why="Un script lit ses arguments par leur rang, et leur nombre à part.",
    lesson=lecon(
        "Dans un script, `$1` est le premier argument, `$2` le deuxième, "
        "et ainsi de suite.",
        "`$#` est leur **nombre**, `$@` la liste complète, `$0` le nom du "
        "script lui-même.",
        "`$0` ne compte pas dans `$#` : le script n'est pas son propre "
        "argument. C'est l'inverse du `argc` du C, qui, lui, le compte.",
        "Les guillemets autour de `\"$@\"` préservent les arguments qui "
        "contiennent des espaces.",
    ),
    dims=(("g", 0, 3), ("n", 2, 4)),
    derive=_arguments,
    tpl="""$ cat infos.sh
#!/bin/bash
echo @expr@
$ ./infos.sh @ligne@""",
    blanks={
        "expr": ("Ce que le script affiche", _opts(
            ("a", '"$#"', lambda p: [str(len(p["args"]))]),
            ("b", '"$@"', lambda p: [" ".join(p["args"])]),
            ("c", '"$1"', lambda p: [p["args"][0]]),
            ("d", '"$0"', lambda _p: ["./infos.sh"]),
        )),
    },
    ref={"expr": "a"},
    rows=lambda p, get: get("expr")(p),
    level=3,
)


# --------------------------------------------------------------------------
# Un message si la commande échoue
# --------------------------------------------------------------------------

def _rapport(p):
    lignes, voisins = RAPPORTS[p["g"]]
    fichiers = ["rapport.txt"] + list(voisins[:p["n"]])
    return {"lignes": list(lignes), "visible": "\n".join(trier(fichiers))}


ERREUR = "cat: absent.txt: No such file or directory"


ENCHAINER = Pattern(
    key="lx_enchainer",
    name="Un message si la commande échoue",
    brief="Lire absent.txt, et n'afficher « pas de fichier » que si la "
          "lecture a échoué.",
    why="Chaque commande rend un code de retour ; && et || s'en servent.",
    lesson=lecon(
        "Toute commande rend un **code de retour** : 0 si elle a réussi, "
        "autre chose sinon.",
        "`a && b` ne lance `b` que si `a` a **réussi**.",
        "`a || b` ne lance `b` que si `a` a **échoué**.",
        "Un message d'erreur part sur la **sortie d'erreur** : il "
        "s'affiche à l'écran même quand la sortie normale est redirigée.",
    ),
    dims=(("g", 0, 3), ("n", 1, 2)),
    derive=_rapport,
    tpl="""$ ls -1
@visible@
$ @cmd@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", 'cat absent.txt || echo "pas de fichier"',
             lambda _p: [ERREUR, "pas de fichier"]),
            ("b", 'cat absent.txt && echo "pas de fichier"',
             lambda _p: [ERREUR]),
            ("c", 'cat rapport.txt || echo "pas de fichier"',
             lambda p: list(p["lignes"])),
            ("d", 'cat rapport.txt && echo "pas de fichier"',
             lambda p: p["lignes"] + ["pas de fichier"]),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=3,
)


# --------------------------------------------------------------------------
# Remplacer un mot partout
# --------------------------------------------------------------------------

def _texte(p):
    nom, lignes = TEXTES[p["g"]]
    return {"nom": nom, "lignes": list(lignes), "contenu": "\n".join(lignes)}


REMPLACER = Pattern(
    key="lx_remplacer",
    name="Remplacer un mot partout",
    brief="Remplacer « chat » par « loup », y compris quand le mot revient "
          "deux fois sur la même ligne.",
    why="Par défaut, sed ne remplace que la première occurrence de chaque ligne.",
    lesson=lecon(
        "`sed 's/motif/remplacement/'` change la **première** occurrence "
        "de chaque ligne, et elle seule.",
        "Le `g` final (*global*) demande toutes les occurrences de la "
        "ligne.",
        "`sed` ne modifie pas le fichier : il écrit le résultat sur la "
        "sortie. Il faut `-i` pour qu'il écrive en place.",
        "`sed -n '2p'` n'affiche que la deuxième ligne, `sed '2d'` "
        "affiche tout sauf elle.",
    ),
    dims=(("g", 0, 3),),
    derive=_texte,
    tpl="""$ cat @nom@
@contenu@
$ @cmd@ @nom@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "sed 's/chat/loup/g'",
             lambda p: [l.replace("chat", "loup") for l in p["lignes"]]),
            ("b", "sed 's/chat/loup/'",
             lambda p: [l.replace("chat", "loup", 1) for l in p["lignes"]]),
            ("c", "sed -n '2p'", lambda p: p["lignes"][1:2]),
            ("d", "sed '2d'",
             lambda p: p["lignes"][:1] + p["lignes"][2:]),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=4,
)


# --------------------------------------------------------------------------
# Le total d'une colonne
# --------------------------------------------------------------------------

def _stock(p):
    nom, lignes = STOCKS[p["g"]]
    return {"nom": nom, "lignes": list(lignes), "contenu": "\n".join(lignes)}


TOTAL = Pattern(
    key="lx_total",
    name="Le total d'une colonne",
    brief="Afficher la somme des nombres de la deuxième colonne, et elle "
          "seule.",
    why="awk traite chaque ligne, puis conclut une fois la dernière lue.",
    lesson=lecon(
        "`awk` découpe chaque ligne en champs : `$1`, `$2`, … et `$NF` "
        "pour le **dernier**.",
        "Le programme entre accolades est exécuté **pour chaque ligne**.",
        "Le bloc `END { … }` ne s'exécute qu'une fois, après la dernière "
        "ligne : c'est là qu'on affiche un total.",
        "Une variable d'`awk` vaut 0 au départ : `s += $2` peut commencer "
        "sans être déclarée.",
    ),
    dims=(("g", 0, 3),),
    derive=_stock,
    tpl="""$ cat @nom@
@contenu@
$ awk @prog@ @nom@""",
    blanks={
        "prog": ("Programme awk", _opts(
            ("a", "'{s += $2} END {print s}'",
             lambda p: [str(sum(int(l.split()[1]) for l in p["lignes"]))]),
            ("b", "'{print $2}'",
             lambda p: [l.split()[1] for l in p["lignes"]]),
            ("c", "'{print $NF}'",
             lambda p: [l.split()[-1] for l in p["lignes"]]),
            ("d", "'{print $1}'",
             lambda p: [l.split()[0] for l in p["lignes"]]),
        )),
    },
    ref={"prog": "a"},
    rows=lambda p, get: get("prog")(p),
    level=4,
)


# --------------------------------------------------------------------------
# Une ligne par fichier
# --------------------------------------------------------------------------

def _glob(p):
    fichiers = list(GLOBS[p["g"]])
    return {"fichiers": fichiers, "visible": "\n".join(trier(fichiers))}


def _pour_chaque(garde):
    return lambda p: ["-- %s" % f for f in trier(p["fichiers"]) if garde(f)]


POUR_CHAQUE = Pattern(
    key="lx_pour_chaque",
    name="Une ligne par fichier",
    brief="Afficher une ligne par fichier .txt du dossier, préfixée de "
          "deux tirets.",
    why="C'est le shell, et non la boucle, qui développe l'étoile.",
    lesson=lecon(
        "`for f in liste; do … done` répète le corps pour chaque élément "
        "de la liste.",
        "`*.txt` n'est pas donné tel quel à la boucle : le **shell** le "
        "remplace d'abord par les noms qui collent, dans l'ordre "
        "alphabétique.",
        "`*` remplace n'importe quelle suite de caractères, y compris "
        "vide ; `?` remplace **exactement un** caractère.",
        "`$f` est la variable de boucle : elle vaut un nom différent à "
        "chaque tour.",
    ),
    dims=(("g", 0, 3),),
    derive=_glob,
    tpl="""$ ls -1
@visible@
$ for f in @motif@; do echo "-- $f"; done""",
    blanks={
        "motif": ("Liste parcourue par la boucle", _opts(
            ("a", "*.txt", _pour_chaque(lambda f: f.endswith(".txt"))),
            ("b", "*", _pour_chaque(lambda _f: True)),
            ("c", "?.txt",
             _pour_chaque(lambda f: f.endswith(".txt") and len(f) == 5)),
            ("d", "*.md", _pour_chaque(lambda f: f.endswith(".md"))),
        )),
    },
    ref={"motif": "a"},
    rows=lambda p, get: get("motif")(p),
    level=4,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

def _nom_espace(p):
    nom = NOMS_ESPACES[p["g"]]
    lignes = ["un", "deux", "trois", "quatre"][:p["n"]]
    return {"nom": nom, "mots": nom.split(), "lignes": lignes,
            "contenu": "\n".join(lignes)}


BUG_GUILLEMETS = debug_pattern(
    key="lx_bug_guillemets",
    name="Bug : compter les lignes du rapport",
    but="compter les lignes d'un fichier dont le nom contient des espaces",
    defaut="variable non protégée : le shell découpe le nom sur les espaces",
    dims=(("g", 0, 3), ("n", 2, 4)),
    derive=_nom_espace,
    tpl="""#!/bin/bash
cat > "@nom@" <<EOF
@contenu@
EOF
fichier="@nom@"
wc -l $fichier""",
    attendu=lambda p: ["%d %s" % (len(p["lignes"]), p["nom"])],
    obtenu=lambda p: ["wc: %s: No such file or directory" % mot
                      for mot in p["mots"]] + ["0 total"],
    diagnostics=(
        ("a", "`$fichier` n'est pas protégé : le shell remplace la "
              "variable, puis **découpe le résultat sur les espaces**. "
              "`wc` reçoit plusieurs noms au lieu d'un seul.",
         "Exact. La substitution a lieu avant le découpage en mots : le "
         "nom devient autant d'arguments qu'il contient de mots. "
         "`wc -l \"$fichier\"` règle le problème — et c'est pourquoi on "
         "met des guillemets autour de toute variable qui porte un "
         "chemin."),
        ("b", "Le fichier n'a pas été créé : le heredoc a échoué.",
         "Non : le nom est entre guillemets à la création, donc le "
         "fichier existe bel et bien. C'est la ligne suivante qui ne sait "
         "plus le nommer."),
        ("c", "`wc -l` ne sait pas compter les lignes d'un fichier dont "
              "le nom contient une espace.",
         "Non : `wc` reçoit ses noms tout faits, et une espace dans un "
         "nom ne le gêne pas. Regardez les noms qu'il annonce dans son "
         "message : ce ne sont pas ceux du fichier."),
        ("d", "Il manque un `$` devant `fichier` à l'affectation.",
         "Non : une affectation s'écrit sans `$`, c'est la lecture qui en "
         "prend un. Cette ligne est correcte."),
    ),
    bonne="a",
    level=4,
)


# --------------------------------------------------------------------------
# Prédiction
# --------------------------------------------------------------------------

PREDIRE_POUR_CHAQUE = predict_from(
    POUR_CHAQUE,
    key="lx_predire_pour_chaque",
    name="Prédire : la boucle sur les fichiers",
    why="Développer l'étoile soi-même, puis dérouler la boucle.",
    level=4,
    dims=(("g", 0, 3),),
)


PATTERNS = (ARGS, ENCHAINER, REMPLACER, TOTAL, POUR_CHAQUE,
            BUG_GUILLEMETS, PREDIRE_POUR_CHAQUE)

MODULE = Module(
    key="linux_shell",
    title="Le shell : variables et enchaînements",
    level=4,
    summary="Les arguments d'un script, les codes de retour avec && et ||, "
            "les boucles et les étoiles, puis sed et awk.",
    keys=tuple(p.key for p in PATTERNS),
)
