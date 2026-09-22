"""Module « Droits et recherche » : chmod, ls -l, find.

Deux questions d'administration quotidienne : qui a le droit de faire
quoi sur un fichier, et comment retrouver un fichier dans une
arborescence sans savoir où il est.
"""

from fnmatch import fnmatch

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from
from .linux_commun import lecon

# Fichiers et leur fiche d'état civil. Le jour est à deux chiffres : `ls`
# l'aligne sur deux colonnes, et un jour seul y prendrait une espace de
# plus que l'élève ne verrait pas.
SCRIPTS = (
    ("sauvegarde.sh", "ada", 128, "Sep 22 12:28"),
    ("deploie.sh", "linus", 96, "Oct 14 09:05"),
    ("nettoyer.sh", "grace", 212, "Nov 30 17:41"),
    ("lancer.sh", "alan", 64, "Dec 11 08:20"),
)

# Droits de départ de l'exercice symbolique. Chacun doit donner quatre
# résultats distincts aux quatre options du menu.
DEPARTS = ("664", "644", "640", "660")

MESSAGES = ("bonjour", "sauvegarde terminee", "rien a faire", "tout est pret")

# Arborescences. Chacune porte un `.log` à la racine et un autre plus bas
# — sans quoi `rm *.log` et `find -delete` se ressembleraient — et un nom
# qui contient « log » sans finir par « .log ».
ARBRES = (
    (("docs", True), ("docs/guide.md", False), ("erreurs.log", False),
     ("logs", True), ("logs/vieux.txt", False), ("notes.txt", False),
     ("src", True), ("src/debug.log", False), ("src/main.c", False)),
    (("build", True), ("build/sortie.log", False),
     ("catalogue.log", False), ("images", True),
     ("images/logo.png", False), ("lisezmoi.md", False),
     ("web", True), ("web/index.html", False)),
    (("archives", True), ("archives/2023.log", False),
     ("cron.log", False), ("notes.md", False), ("scripts", True),
     ("scripts/backlog.txt", False), ("scripts/purge.sh", False)),
    (("data", True), ("data/export.csv", False), ("dialog.txt", False),
     ("journaux", True), ("journaux/acces.log", False),
     ("systeme.log", False)),
)


def _rwx(mode):
    """Les droits d'un mode octal, tels que `ls -l` les écrit."""
    lettres = "-"
    for chiffre in mode:
        n = int(chiffre)
        lettres += "r" if n & 4 else "-"
        lettres += "w" if n & 2 else "-"
        lettres += "x" if n & 1 else "-"
    return lettres


def _symbolique(mode, qui, signe, droit):
    """Applique un changement symbolique du genre `u+x` à un mode octal.

    `qui` est une suite de u, g, o (ou ugo pour « a »), `signe` un + ou un
    -, `droit` la lettre r, w ou x.
    """
    bit = {"r": 4, "w": 2, "x": 1}[droit]
    rangs = {"u": 0, "g": 1, "o": 2}
    chiffres = [int(c) for c in mode]
    for lettre in qui:
        rang = rangs[lettre]
        if signe == "+":
            chiffres[rang] |= bit
        else:
            chiffres[rang] &= ~bit
    return "".join(str(c) for c in chiffres)


def _ls_l(p, mode):
    """La ligne que `ls -l` rend pour le fichier tiré, sous ce mode."""
    return "%s 1 %s %s %d %s %s" % (_rwx(mode), p["user"], p["user"],
                                    p["taille"], p["date"], p["nom"])


def _script(p):
    nom, user, taille, date = SCRIPTS[p["g"]]
    return {"nom": nom, "user": user, "taille": taille, "date": date}


def _script_depart(p):
    params = _script(p)
    params["mode"] = DEPARTS[p["d"]]
    params["avant"] = _ls_l(params, params["mode"])
    return params


def _arbre(p):
    entrees = ARBRES[p["g"]]
    return {"chemins": ["./" + c for c, _d in entrees],
            "dossiers": ["./" + c for c, d in entrees if d],
            "avant": "\n".join(sorted(["."] + ["./" + c for c, _d in entrees]))}


def _trouve(garde):
    """Sortie de `find . … | sort` : les chemins que le prédicat retient."""
    def rows(p):
        candidats = ["."] + p["chemins"]
        return sorted(c for c in candidats if garde(c, p))
    return rows


# --------------------------------------------------------------------------
# Rendre un script exécutable
# --------------------------------------------------------------------------

CHMOD_OCTAL = Pattern(
    key="lx_chmod_octal",
    name="Rendre un script exécutable",
    brief="Donner au script les droits 755 : tout lire et exécuter, mais "
          "le seul propriétaire peut le modifier.",
    why="Trois chiffres, trois publics : propriétaire, groupe, autres.",
    lesson=lecon(
        "`ls -l` montre les droits en tête de ligne : `-rw-r--r--`. Le "
        "premier caractère dit le type (`-` fichier, `d` dossier), puis "
        "viennent trois groupes de `rwx`.",
        "Les trois groupes sont, dans l'ordre : le **propriétaire**, le "
        "**groupe**, les **autres**.",
        "En octal, chaque chiffre est une somme : `r` vaut 4, `w` vaut 2, "
        "`x` vaut 1. Donc 7 = rwx, 6 = rw-, 5 = r-x, 4 = r--.",
        "`chmod 755 fichier` remplace les droits d'un coup, il ne les "
        "ajoute pas.",
    ),
    dims=(("g", 0, 3),),
    derive=lambda p: dict(_script(p),
                          avant=_ls_l(_script(p), "644")),
    tpl="""$ ls -l @nom@
@avant@
$ chmod @mode@ @nom@
$ ls -l @nom@""",
    blanks={
        "mode": ("Mode à donner à chmod", _opts(
            ("a", "755", lambda p: "755"),
            ("b", "644", lambda p: "644"),
            ("c", "700", lambda p: "700"),
            ("d", "777", lambda p: "777"),
        )),
    },
    ref={"mode": "a"},
    rows=lambda p, get: [_ls_l(p, get("mode")(p))],
    level=3,
)


# --------------------------------------------------------------------------
# Un droit en plus, pour une seule personne
# --------------------------------------------------------------------------

CHMOD_SYMBOLIQUE = Pattern(
    key="lx_chmod_symbolique",
    name="Un droit en plus, pour le seul propriétaire",
    brief="Ajouter le droit d'exécution au propriétaire, sans toucher aux "
          "droits du groupe ni des autres.",
    why="La forme symbolique modifie les droits en place, au lieu de les "
        "remplacer.",
    lesson=lecon(
        "La forme symbolique s'écrit **qui**, **signe**, **droit** : "
        "`u+x` ajoute `x` au propriétaire (*user*).",
        "`g` est le groupe, `o` les autres (*others*), `a` tout le monde.",
        "`+` ajoute, `-` retire, `=` fixe exactement.",
        "Contrairement à la forme octale, elle ne touche qu'aux droits "
        "nommés : tout le reste est conservé.",
    ),
    dims=(("g", 0, 3), ("d", 0, 3)),
    derive=_script_depart,
    tpl="""$ ls -l @nom@
@avant@
$ chmod @droit@ @nom@
$ ls -l @nom@""",
    blanks={
        "droit": ("Changement à appliquer", _opts(
            ("a", "u+x", lambda p: _symbolique(p["mode"], "u", "+", "x")),
            ("b", "a+x", lambda p: _symbolique(p["mode"], "ugo", "+", "x")),
            ("c", "g-w", lambda p: _symbolique(p["mode"], "g", "-", "w")),
            ("d", "o+w", lambda p: _symbolique(p["mode"], "o", "+", "w")),
        )),
    },
    ref={"droit": "a"},
    rows=lambda p, get: [_ls_l(p, get("droit")(p))],
    level=3,
)


# --------------------------------------------------------------------------
# Retrouver des fichiers par leur nom
# --------------------------------------------------------------------------

TROUVER = Pattern(
    key="lx_trouver",
    name="Retrouver des fichiers par leur nom",
    brief="N'afficher que les chemins dont le nom se termine par « .log ».",
    why="find descend dans toute l'arborescence ; le prédicat dit quoi garder.",
    lesson=lecon(
        "`find dossier` descend dans tout ce qu'il contient, aussi "
        "profond qu'il faut.",
        "`-name '*.log'` ne garde que les entrées dont le **nom** colle au "
        "motif. Les apostrophes empêchent le shell de développer l'étoile "
        "avant que `find` ne la voie.",
        "`-type f` ne garde que les fichiers, `-type d` que les dossiers.",
        "`| sort` range la sortie : l'ordre naturel de `find` dépend du "
        "disque, celui de `sort` est toujours le même.",
    ),
    dims=(("g", 0, 3),),
    derive=_arbre,
    tpl="""$ find . | sort
@avant@
$ find . @predicat@ | sort""",
    blanks={
        "predicat": ("Critère de recherche", _opts(
            ("a", "-name '*.log'",
             _trouve(lambda c, _p: fnmatch(c.rsplit("/", 1)[-1], "*.log"))),
            ("b", "-type f",
             _trouve(lambda c, p: c != "." and c not in p["dossiers"])),
            ("c", "-type d",
             _trouve(lambda c, p: c == "." or c in p["dossiers"])),
            ("d", "-name '*log*'",
             _trouve(lambda c, _p: fnmatch(c.rsplit("/", 1)[-1], "*log*"))),
        )),
    },
    ref={"predicat": "a"},
    rows=lambda p, get: get("predicat")(p),
    level=3,
)


# --------------------------------------------------------------------------
# Faire le ménage
# --------------------------------------------------------------------------

def _apres_suppression(garde):
    """Arborescence restante, une fois supprimé ce que `garde` désigne."""
    def rows(p):
        restants = [c for c in p["chemins"] if not garde(c, p)]
        return sorted(["."] + restants)
    return rows


def _est_log(chemin):
    return chemin.rsplit("/", 1)[-1].endswith(".log")


MENAGE = Pattern(
    key="lx_menage",
    name="Faire le ménage",
    brief="Supprimer tous les fichiers .log de l'arborescence, où qu'ils "
          "soient, puis afficher ce qu'il reste.",
    why="Une étoile du shell ne descend pas dans les sous-dossiers ; find, si.",
    lesson=lecon(
        "`rm *.log` ne voit que le dossier courant : l'étoile est "
        "développée par le **shell**, qui ne descend pas tout seul.",
        "`find . -name '*.log' -delete` traverse l'arborescence entière et "
        "supprime chaque entrée trouvée.",
        "Un `find` destructeur se relit toujours **sans** `-delete` "
        "d'abord : la liste affichée est exactement ce qui va disparaître.",
        "`-type f -delete` supprimerait tous les fichiers, quels qu'ils "
        "soient. Le prédicat est la seule barrière.",
    ),
    dims=(("g", 0, 3),),
    derive=_arbre,
    tpl="""$ find . | sort
@avant@
$ @cmd@
$ find . | sort""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "find . -name '*.log' -delete",
             _apres_suppression(lambda c, _p: _est_log(c))),
            ("b", "find . -name '*.log' | sort",
             lambda p: (sorted(c for c in p["chemins"] if _est_log(c))
                        + sorted(["."] + list(p["chemins"])))),
            ("c", "find . -type f -delete",
             _apres_suppression(lambda c, p: c not in p["dossiers"])),
            ("d", "rm *.log",
             _apres_suppression(
                 lambda c, _p: _est_log(c) and c.count("/") == 1)),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=4,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

BUG_CHMOD = debug_pattern(
    key="lx_bug_chmod",
    name="Bug : le script qui ne démarre pas",
    but="écrire un petit script, puis le lancer",
    defaut="droits 644 : le fichier est lisible mais pas exécutable",
    dims=(("g", 0, 3),),
    derive=lambda p: {"mot": MESSAGES[p["g"]]},
    tpl="""#!/bin/bash
# essai.sh
cat > salut.sh <<EOF
#!/bin/bash
echo @mot@
EOF
chmod 644 salut.sh
./salut.sh""",
    attendu=lambda p: [p["mot"]],
    obtenu=lambda _p: ["essai.sh: line 8: ./salut.sh: Permission denied"],
    diagnostics=(
        ("a", "644 ne donne à personne le droit d'**exécution** : le "
              "fichier est lisible, mais le shell refuse de le lancer. Il "
              "faudrait 755, ou `chmod u+x`.",
         "Exact. 6 vaut rw-, 4 vaut r-- : pas un seul `x` dans le lot. "
         "Écrire un script ne suffit pas à en faire un programme, il faut "
         "encore le rendre exécutable."),
        ("b", "La ligne `#!/bin/bash` manque dans salut.sh.",
         "Non : le heredoc l'écrit bien en première ligne. Et même sans "
         "elle, le shell lancerait le fichier avec son propre interpréteur."),
        ("c", "Le heredoc n'a pas été fermé correctement.",
         "Non : le `EOF` de fin est bien là. Si le heredoc était ouvert, "
         "le shell se plaindrait d'un document en attente, et pas d'un "
         "droit refusé."),
        ("d", "Il faut écrire `bash salut.sh` : un script ne se lance "
              "jamais par son chemin.",
         "Le détour marcherait — `bash salut.sh` ne demande que le droit "
         "de **lecture** — mais ce n'est pas la cause de l'écart. Le "
         "message parle d'une permission refusée sur `./salut.sh`."),
    ),
    bonne="a",
    level=3,
)


# --------------------------------------------------------------------------
# Prédiction
# --------------------------------------------------------------------------

PREDIRE_CHMOD = predict_from(
    CHMOD_SYMBOLIQUE,
    key="lx_predire_chmod",
    name="Prédire : les droits après un chmod",
    why="Traduire trois chiffres en neuf lettres, puis n'en changer qu'une.",
    level=4,
    dims=(("g", 0, 3), ("d", 0, 3)),
)


PATTERNS = (CHMOD_OCTAL, CHMOD_SYMBOLIQUE, TROUVER, MENAGE,
            BUG_CHMOD, PREDIRE_CHMOD)

MODULE = Module(
    key="linux_droits",
    title="Droits et recherche",
    level=3,
    summary="Lire et changer les droits d'un fichier avec ls -l et chmod, "
            "et retrouver ce qu'on cherche dans une arborescence avec find.",
    keys=tuple(p.key for p in PATTERNS),
)
