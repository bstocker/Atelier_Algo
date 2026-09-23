"""Module « Filtrer, trier, compter » : grep, cut, sort, uniq et les tubes.

Le cœur de la ligne de commande : chaque outil fait une chose, et le
tube `|` les enchaîne. Un élève qui sait composer `sort | uniq -c | sort
-rn` a compris l'essentiel de la philosophie Unix.

Les exercices dont le menu cite un nom de fichier le gardent **fixe** :
une option est un texte figé, elle ne peut pas suivre le tirage. C'est
alors le contenu du fichier qui change d'un élève à l'autre.
"""

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from
from .linux_commun import compte, lecon, paquets, predire

# Journaux mêlant « Erreur » et « erreur » : sans les deux casses, l'option
# -i ne se distinguerait pas d'une recherche ordinaire.
LOGS = (
    ("systeme.log", ("Erreur disque plein", "demarrage termine",
                     "erreur reseau", "service pret", "erreur droits")),
    ("appli.log", ("connexion acceptee", "Erreur de saisie",
                   "page envoyee", "erreur de format", "fin de session")),
    ("cron.log", ("tache lancee", "erreur de script", "tache terminee",
                  "Erreur de permission", "rapport ecrit")),
    ("web.log", ("requete recue", "Erreur 404", "page servie",
                 "erreur 500", "cache vide")),
)

# Fichiers à colonnes, séparées par deux-points comme /etc/passwd.
TABLES = (
    ("comptes.txt", ("ada:x:1001:/home/ada", "linus:x:1002:/home/linus",
                     "grace:x:1003:/home/grace")),
    ("equipes.txt", ("dupont:dev:3:paris", "martin:test:2:lyon",
                     "durand:dev:5:nice")),
    ("stock.txt", ("vis:boite:120:atelier", "clou:sachet:400:reserve",
                   "ecrou:boite:75:atelier")),
    ("serveurs.txt", ("alpha:web:8080:actif", "beta:base:5432:arrete",
                      "gamma:cache:6379:actif")),
)

# Nombres écrits en texte. Chaque jeu contient une paire dont l'une est le
# préfixe de l'autre (12 et 120) : sans elle, le tri inverse coïnciderait
# avec le tri numérique. Et un doublon, sans quoi -u ne se verrait pas.
NOMBRES = (
    ("120", "9", "12", "9", "83"),
    ("45", "7", "450", "7", "61"),
    ("30", "8", "300", "8", "25"),
    ("19", "6", "190", "6", "72"),
)

# Doublons non consécutifs : c'est ce qui sépare `uniq` de `sort | uniq`.
DOUBLONS = (
    ("lyon", "paris", "lyon", "nice", "paris", "lyon"),
    ("rouge", "vert", "rouge", "bleu", "vert", "rouge"),
    ("nord", "sud", "nord", "est", "sud", "nord"),
    ("chat", "chien", "chat", "souris", "chien", "chat"),
)

# Journaux d'accès : quatre valeurs, comptées 4, 3, 2 et 1 fois. Des
# comptes tous distincts, sinon `sort -rn` départagerait les ex æquo sur
# la ligne entière et l'ordre deviendrait difficile à prévoir.
ACCES = (
    ("lyon", "paris", "lyon", "nice", "paris", "lyon", "brest", "nice",
     "paris", "lyon"),
    ("accueil", "tarifs", "contact", "accueil", "tarifs", "accueil",
     "aide", "contact", "tarifs", "accueil"),
    ("firefox", "chrome", "firefox", "safari", "chrome", "firefox",
     "edge", "safari", "chrome", "firefox"),
    ("ssh", "http", "ssh", "ftp", "http", "ssh", "dns", "ftp", "http",
     "ssh"),
)


def _fichier(jeux):
    """Jeu tiré : le nom du fichier, ses lignes, et le `cat` qui les montre."""
    def derive(p):
        nom, lignes = jeux[p["g"]]
        return {"nom": nom, "lignes": list(lignes),
                "contenu": "\n".join(lignes)}
    return derive


def _lignes(jeux):
    """Même chose, pour les exercices dont le nom de fichier est fixe."""
    def derive(p):
        lignes = list(jeux[p["g"]])
        return {"lignes": lignes, "contenu": "\n".join(lignes)}
    return derive


# --------------------------------------------------------------------------
# Chercher sans se soucier de la casse
# --------------------------------------------------------------------------

CHERCHER = Pattern(
    key="lx_chercher",
    name="Chercher un mot dans un journal",
    brief="Afficher les lignes qui parlent d'erreur, avec ou sans majuscule.",
    why="Le motif est cherché tel quel : une majuscule suffit à le manquer.",
    lesson=lecon(
        "`grep motif fichier` affiche les lignes qui **contiennent** le "
        "motif.",
        "La recherche distingue les majuscules des minuscules. `-i` "
        "(*ignore case*) lui dit de ne pas en tenir compte.",
        "`-v` (*invert*) garde au contraire les lignes qui **ne** "
        "contiennent **pas** le motif.",
        "`-c` (*count*) n'affiche plus les lignes, mais leur nombre.",
    ),
    dims=(("g", 0, 3),),
    derive=_fichier(LOGS),
    tpl="""$ cat @nom@
@contenu@
$ @cmd@ erreur @nom@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "grep -i",
             lambda p: [l for l in p["lignes"] if "erreur" in l.lower()]),
            ("b", "grep",
             lambda p: [l for l in p["lignes"] if "erreur" in l]),
            ("c", "grep -v",
             lambda p: [l for l in p["lignes"] if "erreur" not in l]),
            ("d", "grep -c",
             lambda p: [str(len([l for l in p["lignes"]
                                 if "erreur" in l]))]),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=2,
)


# --------------------------------------------------------------------------
# Extraire une colonne
# --------------------------------------------------------------------------

def _colonnes(champs):
    """Extrait des champs séparés par deux-points, à la façon de cut."""
    return lambda p: [":".join(l.split(":")[i - 1] for i in champs)
                      for l in p["lignes"]]


COLONNE = Pattern(
    key="lx_colonne",
    name="Extraire une colonne",
    brief="N'afficher que la première colonne, celle d'avant le premier « : ».",
    why="Un fichier à colonnes se découpe : encore faut-il dire sur quoi.",
    lesson=lecon(
        "`cut` découpe chaque ligne en champs. `-f1` demande le premier.",
        "`-d` donne le **séparateur**. Sans lui, `cut` découpe sur les "
        "tabulations — et une ligne sans tabulation ressort entière.",
        "`-f1,3` prend deux champs, qu'il recolle avec le séparateur.",
        "Le deux-points est le séparateur historique d'Unix : c'est celui "
        "de `/etc/passwd`.",
    ),
    dims=(("g", 0, 3),),
    derive=_fichier(TABLES),
    tpl="""$ cat @nom@
@contenu@
$ cut @opt@ @nom@""",
    blanks={
        "opt": ("Options de cut", _opts(
            ("a", "-d: -f1", _colonnes((1,))),
            ("b", "-d: -f3", _colonnes((3,))),
            ("c", "-d: -f1,3", _colonnes((1, 3))),
            ("d", "-f1", lambda p: list(p["lignes"])),
        )),
    },
    ref={"opt": "a"},
    rows=lambda p, get: get("opt")(p),
    level=2,
)


# --------------------------------------------------------------------------
# Trier des nombres
# --------------------------------------------------------------------------

TRIER = Pattern(
    key="lx_trier",
    name="Trier des nombres",
    brief="Trier ces valeurs de la plus petite à la plus grande.",
    why="Sans option, sort compare des textes : 9 arrive après 120.",
    lesson=lecon(
        "`sort` trie **comme un dictionnaire**, caractère par caractère. "
        "« 12 » vient donc avant « 9 », comme « ab » avant « b ».",
        "`-n` (*numeric*) lui dit de lire les lignes comme des nombres.",
        "`-r` (*reverse*) inverse l'ordre obtenu.",
        "`-u` (*unique*) ne garde qu'un exemplaire de chaque valeur.",
    ),
    dims=(("g", 0, 3),),
    derive=_lignes(NOMBRES),
    tpl="""$ cat nombres.txt
@contenu@
$ @cmd@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "sort -n nombres.txt",
             lambda p: sorted(p["lignes"], key=int)),
            ("b", "sort nombres.txt", lambda p: sorted(p["lignes"])),
            ("c", "sort -r nombres.txt",
             lambda p: sorted(p["lignes"], reverse=True)),
            ("d", "sort -u nombres.txt", lambda p: sorted(set(p["lignes"]))),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=2,
)


# --------------------------------------------------------------------------
# Une fois chaque valeur
# --------------------------------------------------------------------------

DEDOUBLONNER = Pattern(
    key="lx_dedoublonner",
    name="Une fois chaque valeur",
    brief="Afficher chaque valeur du fichier une seule fois, par ordre "
          "alphabétique.",
    why="uniq ne regarde que la ligne précédente. Il faut donc trier avant.",
    lesson=lecon(
        "`uniq` supprime les répétitions **consécutives**, et elles seules.",
        "Deux valeurs identiques séparées par une autre ligne lui échappent "
        "donc : d'où le `sort` qui le précède presque toujours.",
        "`|` est le **tube** : il branche la sortie de gauche sur l'entrée "
        "de droite, sans passer par un fichier.",
        "`uniq -d` fait l'inverse du travail demandé ici : il ne garde que "
        "les valeurs qui apparaissent plusieurs fois.",
    ),
    dims=(("g", 0, 3),),
    derive=_lignes(DOUBLONS),
    tpl="""$ cat liste.txt
@contenu@
$ @cmd@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "sort liste.txt | uniq",
             lambda p: sorted(set(p["lignes"]))),
            ("b", "uniq liste.txt",
             lambda p: [t for _n, t in paquets(p["lignes"])]),
            ("c", "sort liste.txt", lambda p: sorted(p["lignes"])),
            ("d", "sort liste.txt | uniq -d",
             lambda p: sorted(v for v in set(p["lignes"])
                              if p["lignes"].count(v) > 1)),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=3,
)


# --------------------------------------------------------------------------
# Le palmarès des accès
# --------------------------------------------------------------------------

def _classement(p):
    lignes = p["lignes"]
    return [compte(lignes.count(v), v)
            for v in sorted(set(lignes), key=lambda v: (-lignes.count(v), v))]


def _alphabetique(p):
    lignes = p["lignes"]
    return [compte(lignes.count(v), v) for v in sorted(set(lignes))]


PALMARES = Pattern(
    key="lx_palmares",
    name="Le palmarès des accès",
    brief="Afficher les trois valeurs les plus fréquentes, la plus "
          "fréquente en tête, chacune précédée de son nombre d'occurrences.",
    why="Quatre outils à enchaîner, et l'ordre du tube fait tout le résultat.",
    lesson=lecon(
        "`uniq -c` compte les groupes qu'il réduit, et écrit le nombre "
        "**devant** la ligne, aligné sur sept colonnes.",
        "`sort -rn` trie ces lignes sur ce nombre, du plus grand au plus "
        "petit : `-n` pour le lire comme un nombre, `-r` pour descendre.",
        "`head -n 3` coupe après trois lignes.",
        "Chaque maillon suppose le précédent : sans le `sort` du début, "
        "les comptes sont faux ; sans `uniq -c`, il n'y a rien à trier.",
    ),
    dims=(("g", 0, 3),),
    derive=_lignes(ACCES),
    tpl="""$ cat acces.log
@contenu@
$ @cmd@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "sort acces.log | uniq -c | sort -rn | head -n 3",
             lambda p: _classement(p)[:3]),
            ("b", "sort acces.log | uniq -c | head -n 3",
             lambda p: _alphabetique(p)[:3]),
            ("c", "uniq -c acces.log | head -n 3",
             lambda p: [compte(n, t) for n, t in paquets(p["lignes"])][:3]),
            ("d", "sort acces.log | uniq | head -n 3",
             lambda p: sorted(set(p["lignes"]))[:3]),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=4,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

BUG_UNIQ = debug_pattern(
    key="lx_bug_uniq",
    name="Bug : la liste sans doublon",
    but="afficher une fois chaque valeur du fichier, par ordre alphabétique",
    defaut="uniq sans sort : seuls les doublons consécutifs disparaissent",
    dims=(("g", 0, 3),),
    derive=_lignes(DOUBLONS),
    tpl="""#!/bin/bash
cat > liste.txt <<EOF
@contenu@
EOF
uniq liste.txt""",
    attendu=lambda p: sorted(set(p["lignes"])),
    obtenu=lambda p: [t for _n, t in paquets(p["lignes"])],
    diagnostics=(
        ("a", "`uniq` ne supprime que les doublons **consécutifs**. Les "
              "valeurs répétées à distance lui échappent : il faudrait "
              "trier avant, avec `sort liste.txt | uniq`.",
         "Exact. `uniq` ne compare chaque ligne qu'à la précédente : il ne "
         "garde que le premier exemplaire de chaque **suite** identique. "
         "Trier d'abord rapproche les doublons, et c'est pourquoi les deux "
         "commandes vont presque toujours ensemble."),
        ("b", "`uniq` attend son entrée par un tube, pas un nom de fichier.",
         "Non : `uniq fichier` est correct, et le fichier est bien lu. "
         "C'est ce que `uniq` en retire qui ne suffit pas."),
        ("c", "Le heredoc n'a pas écrit toutes les lignes dans le fichier.",
         "Non : la sortie contient les valeurs dans leur ordre d'écriture, "
         "toutes présentes au moins une fois. Le fichier est donc complet."),
        ("d", "Il faudrait `uniq -u` pour n'afficher chaque valeur "
              "qu'une seule fois.",
         "Non : `-u` ne garde que les lignes qui ne sont **jamais** "
         "répétées, et en supprimerait donc encore davantage. Le manque "
         "est ailleurs : avant `uniq`."),
    ),
    bonne="a",
    level=3,
)


# --------------------------------------------------------------------------
# Prédiction
# --------------------------------------------------------------------------

PREDIRE_COLONNE = predict_from(
    COLONNE,
    key="lx_predire_colonne",
    name="Prédire : le découpage en colonnes",
    why="Compter les champs d'une ligne, séparateur en main.",
    level=3,
    output_format=(
        "<champ>",
        "<champ>",
        "…",
    ),
    dims=(("g", 0, 3),),
    lesson=predire(COLONNE),
)


PATTERNS = (CHERCHER, COLONNE, TRIER, DEDOUBLONNER, PALMARES,
            BUG_UNIQ, PREDIRE_COLONNE)

MODULE = Module(
    key="linux_filtres",
    title="Filtrer, trier, compter",
    level=2,
    summary="grep, cut, sort, uniq, head, et le tube qui les enchaîne : "
            "extraire d'un fichier exactement ce qu'on cherche.",
    keys=tuple(p.key for p in PATTERNS),
)
