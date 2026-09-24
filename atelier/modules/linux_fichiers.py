"""Module « Fichiers et dossiers » : se repérer, lister, copier, rediriger.

Le premier contact avec le terminal : où suis-je, qu'y a-t-il ici, que
devient un fichier quand on le déplace, et où va ce qu'une commande
affiche. Tout le chapitre repose sur ces quatre questions.
"""

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from
from .linux_commun import lecon, listing, predire, trier

# Dossiers personnels : deux entrées cachées, deux visibles. Les noms sont
# choisis pour que l'ordre de `ls` soit le même avec ou sans le point de
# tête (cf. `trier`).
DOSSIERS = (
    ("ada", (".bashrc", ".config"), ("notes.txt", "rapport.pdf")),
    ("linus", (".cache", ".gitconfig"), ("kernel.c", "todo.md")),
    ("grace", (".bash_history", ".env"), ("manuel.pdf", "notes.txt")),
    ("alan", (".alias", ".config"), ("machine.txt", "notes.md")),
)

# `ls -l` des entrées visibles de chaque dossier : taille et date de
# modification, dans l'ordre de DOSSIERS. Toutes les tailles restent sous
# 4 096 octets : chaque fichier occupe alors un bloc, compté 4 par
# `total`.
DETAILS = (
    ((812, "Sep 12 10:15"), (3406, "Sep 18 16:40")),
    ((2210, "Sep 10 09:02"), (145, "Sep 21 18:30")),
    ((3977, "Aug 29 14:12"), (530, "Sep 15 11:48")),
    ((1204, "Sep 16 08:55"), (96, "Sep 20 17:05")),
)

# Chemins courants, tous à deux crans au moins sous le dossier personnel :
# sans cela `..` et `~` mèneraient au même endroit.
CHEMINS = (
    ("ada", "projet/src"),
    ("linus", "kernel/drivers"),
    ("grace", "cobol/tests"),
    ("alan", "machine/notes"),
)

# Fichiers à compter. Dans chacun, le nombre de lignes, de mots, d'octets
# et la longueur de la plus longue ligne sont quatre valeurs distinctes :
# sinon deux options rendraient la même sortie.
TEXTES = (
    ("courses.txt", ("pain", "lait demi ecreme", "oeufs", "riz complet")),
    ("outils.txt", ("marteau", "scie a metaux", "vis", "cle plate",
                    "niveau")),
    ("taches.txt", ("reunion", "relire le rapport", "mail")),
    ("villes.txt", ("lyon", "saint denis", "nice", "le mans", "tours",
                    "brest")),
)

JOURNAUX = (
    ("journal.log", ("demarrage du service", "lecture de la configuration",
                     "connexion de ada", "envoi du rapport",
                     "connexion de linus", "rotation des journaux",
                     "arret du service")),
    ("suivi.log", ("ouverture de la base", "index reconstruit",
                   "sauvegarde lancee", "sauvegarde terminee",
                   "cache vide", "nouvelle session", "fermeture")),
    ("acces.log", ("page accueil", "page tarifs", "page contact",
                   "formulaire envoye", "page accueil", "deconnexion",
                   "session expiree")),
    ("build.log", ("compilation de main.c", "compilation de util.c",
                   "edition des liens", "tests unitaires",
                   "tests d integration", "paquet construit",
                   "archive deposee")),
)

# Fichiers qui traînent à côté du rapport. Ils ne changent rien au
# raisonnement, mais donnent à chaque élève sa propre sortie.
VOISINS = (
    ("agenda.txt", "brouillon.md"),
    ("budget.csv", "contrat.pdf"),
    ("annexe.txt", "devis.odt"),
    ("bilan.md", "courrier.txt"),
)

REDIRECTIONS = (
    ("agenda.txt", "lundi", "mardi"),
    ("liste.txt", "pain", "lait"),
    ("todo.txt", "reunion", "rapport"),
    ("noms.txt", "ada", "grace"),
)

SEMAINES = (
    ("lundi", "mardi", "mercredi", "jeudi", "vendredi"),
    ("janvier", "fevrier", "mars", "avril", "mai"),
    ("nord", "sud", "est", "ouest", "centre"),
    ("alpha", "beta", "gamma", "delta", "epsilon"),
)


# --------------------------------------------------------------------------
# Les fichiers cachés
# --------------------------------------------------------------------------

def _dossier(p):
    user, caches, visibles = DOSSIERS[p["g"]]
    return {"user": user, "caches": list(caches), "visibles": list(visibles),
            "visible": "\n".join(trier(visibles))}


CACHES = Pattern(
    key="lx_caches",
    name="Les fichiers cachés",
    brief="Afficher toutes les entrées du dossier, y compris « . » et « .. ».",
    why="Un nom qui commence par un point ne sort pas de lui-même.",
    lesson=lecon(
        "Un fichier dont le nom commence par un **point** est dit caché : "
        "`ls` ne le montre pas.",
        "`-a` (*all*) montre tout, **y compris** `.` (le dossier courant) "
        "et `..` (le dossier parent).",
        "`-A` montre la même chose **sans** `.` ni `..`. C'est toute la "
        "différence entre les deux options.",
        "`-1` (le **chiffre** un, pas la lettre `l`) demande un nom par "
        "ligne, au lieu des colonnes habituelles, et `-r` renverse l'ordre.",
    ),
    dims=(("g", 0, 3),),
    derive=_dossier,
    tpl="""$ pwd
/home/@user@
$ ls -1
@visible@
$ @cmd@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "ls -1a",
             lambda p: [".", ".."] + trier(p["caches"] + p["visibles"])),
            ("b", "ls -1", lambda p: trier(p["visibles"])),
            ("c", "ls -1A", lambda p: trier(p["caches"] + p["visibles"])),
            ("d", "ls -1Ar",
             lambda p: trier(p["caches"] + p["visibles"])[::-1]),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=1,
)


# --------------------------------------------------------------------------
# Un nom par ligne
# --------------------------------------------------------------------------

def _long(p):
    """`ls -l` du dossier tiré : les tailles s'alignent à droite."""
    user, _caches, visibles = DOSSIERS[p["g"]]
    details = DETAILS[p["g"]]
    largeur = max(len(str(taille)) for taille, _date in details)
    lignes = ["-rw-r--r-- 1 %s %s %*d %s %s"
              % (user, user, largeur, taille, date, nom)
              for nom, (taille, date) in zip(visibles, details)]
    return ["total %d" % (4 * len(visibles))] + lignes


def _details(p):
    params = _dossier(p)
    params["long"] = "\n".join(_long(p))
    return params


UN_PAR_LIGNE = Pattern(
    key="lx_un_par_ligne",
    name="Un nom par ligne",
    brief="Afficher seulement les noms, un par ligne, sans les détails.",
    why="`-1` et `-l` se ressemblent à l'œil, pas dans le terminal.",
    lesson=lecon(
        "`ls -l` — la **lettre** L minuscule, pour *long* — détaille chaque "
        "entrée : droits, propriétaire, groupe, taille, date de "
        "modification, puis le nom.",
        "`ls -1` — le **chiffre** un — n'affiche que les noms, un par "
        "ligne.",
        "Dans beaucoup de polices, `l` et `1` se ressemblent : fiez-vous à "
        "la sortie, pas à la forme de la commande.",
        "La ligne `total` de `ls -l` donne la place occupée sur le disque, "
        "en blocs d'un kilo-octet.",
    ),
    dims=(("g", 0, 3),),
    derive=_details,
    tpl="""$ pwd
/home/@user@
$ ls -l
@long@
$ @cmd@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "ls -1", lambda p: trier(p["visibles"])),
            ("b", "ls -l", _long),
            ("c", "ls -1r", lambda p: trier(p["visibles"])[::-1]),
            ("d", "ls -1A", lambda p: trier(p["caches"] + p["visibles"])),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=1,
)


# --------------------------------------------------------------------------
# Remonter d'un cran
# --------------------------------------------------------------------------

def _chemin(p):
    user, sous = CHEMINS[p["g"]]
    return {"user": user, "chemin": "/home/%s/%s" % (user, sous)}


PARENT = Pattern(
    key="lx_parent",
    name="Remonter d'un cran",
    brief="Se placer dans le dossier qui contient le dossier courant.",
    why="Un chemin se lit de gauche à droite ; « .. » revient sur ses pas.",
    lesson=lecon(
        "`pwd` (*print working directory*) affiche le dossier où l'on se "
        "trouve.",
        "`.` désigne le dossier courant, `..` le dossier **parent**.",
        "`~` est un raccourci pour votre dossier personnel, "
        "`/home/quelqu-un`. Ce n'est pas le parent : c'est un point fixe.",
        "`cd` n'affiche rien quand il réussit. Le silence est bon signe.",
    ),
    dims=(("g", 0, 3),),
    derive=_chemin,
    tpl="""$ pwd
@chemin@
$ cd @cible@
$ pwd""",
    blanks={
        "cible": ("Destination du cd", _opts(
            ("a", "..", lambda p: [p["chemin"].rsplit("/", 1)[0]]),
            ("b", ".", lambda p: [p["chemin"]]),
            ("c", "~", lambda p: ["/home/%s" % p["user"]]),
            ("d", "/", lambda p: ["/"]),
        )),
    },
    ref={"cible": "a"},
    rows=lambda p, get: get("cible")(p),
    level=1,
)


# --------------------------------------------------------------------------
# Compter les lignes
# --------------------------------------------------------------------------

def _texte(p):
    nom, lignes = TEXTES[p["g"]]
    return {"nom": nom, "lignes": list(lignes), "contenu": "\n".join(lignes)}


COMPTER = Pattern(
    key="lx_compter",
    name="Compter les lignes d'un fichier",
    brief="Afficher le nombre de lignes du fichier, et rien d'autre.",
    why="La même commande compte quatre choses : c'est l'option qui tranche.",
    lesson=lecon(
        "`wc` (*word count*) compte, et `-l` (*lines*) demande les lignes.",
        "`-w` compte les **mots**, `-c` les **octets**, `-L` la longueur de "
        "la plus longue ligne.",
        "Quand on lui donne un nom de fichier, `wc` le répète après le "
        "nombre : `4 courses.txt`.",
    ),
    dims=(("g", 0, 3),),
    derive=_texte,
    tpl="""$ cat @nom@
@contenu@
$ wc @opt@ @nom@""",
    blanks={
        "opt": ("Option de wc", _opts(
            ("a", "-l", lambda p: len(p["lignes"])),
            ("b", "-w", lambda p: sum(len(l.split()) for l in p["lignes"])),
            ("c", "-c", lambda p: sum(len(l) + 1 for l in p["lignes"])),
            ("d", "-L", lambda p: max(len(l) for l in p["lignes"])),
        )),
    },
    ref={"opt": "a"},
    rows=lambda p, get: ["%d %s" % (get("opt")(p), p["nom"])],
    level=1,
)


# --------------------------------------------------------------------------
# La fin d'un journal
# --------------------------------------------------------------------------

def _journal(p):
    nom, lignes = JOURNAUX[p["g"]]
    lignes = list(lignes[:p["n"]])
    return {"nom": nom, "lignes": lignes, "contenu": "\n".join(lignes)}


FIN_JOURNAL = Pattern(
    key="lx_fin_journal",
    name="La fin d'un journal",
    brief="Afficher les trois dernières lignes du fichier.",
    why="Un journal se lit par la fin : c'est là que sont les dernières traces.",
    lesson=lecon(
        "`head` montre le **début** d'un fichier, `tail` sa **fin**.",
        "`-n 3` fixe le nombre de lignes. Sans option, les deux en montrent "
        "dix.",
        "Sur un fichier de 200 000 lignes, `tail` reste immédiat : c'est "
        "pour cela qu'on ne l'ouvre pas dans un éditeur.",
    ),
    dims=(("g", 0, 3), ("n", 5, 7)),
    derive=_journal,
    tpl="""$ cat @nom@
@contenu@
$ @cmd@ @nom@""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "tail -n 3", lambda p: p["lignes"][-3:]),
            ("b", "head -n 3", lambda p: p["lignes"][:3]),
            ("c", "tail -n 1", lambda p: p["lignes"][-1:]),
            ("d", "head -n 1", lambda p: p["lignes"][:1]),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=2,
)


# --------------------------------------------------------------------------
# Déplacer sans laisser de copie
# --------------------------------------------------------------------------

def _rangement(p):
    """Le rapport, le dossier de sauvegarde, et quelques voisins.

    Les noms cités par les commandes du menu sont fixes — une option est
    un texte, elle ne peut pas s'adapter au tirage. Ce sont les fichiers
    autour qui changent, et avec eux la sortie de chaque élève.
    """
    voisins = list(VOISINS[p["g"]][:p["n"]])
    return {"voisins": voisins,
            "avant": "\n".join(listing(
                ["rapport.txt", "sauvegarde"] + voisins, "sauvegarde", []))}


def _apres(racine, dedans):
    return lambda p: listing(racine + p["voisins"], "sauvegarde", dedans)


RANGER = Pattern(
    key="lx_ranger",
    name="Ranger le rapport",
    brief="Déplacer rapport.txt dans le dossier sauvegarde, sans en laisser "
          "de copie à la racine.",
    why="Copier et déplacer se ressemblent, mais l'un des deux laisse l'original.",
    lesson=lecon(
        "`cp source destination` **copie** : la source reste en place.",
        "`mv source destination` **déplace** : la source disparaît. C'est "
        "aussi ainsi qu'on renomme un fichier.",
        "Quand la destination est un dossier, le fichier y entre sous son "
        "nom d'origine. Quand c'est un nom, il devient ce nom.",
        "`ls` peut recevoir plusieurs dossiers : il les annonce alors par "
        "leur nom suivi de deux points.",
    ),
    dims=(("g", 0, 3), ("n", 1, 2)),
    derive=_rangement,
    tpl="""$ ls -1 . sauvegarde
@avant@
$ @cmd@
$ ls -1 . sauvegarde""",
    blanks={
        "cmd": ("Commande à taper", _opts(
            ("a", "mv rapport.txt sauvegarde/",
             _apres(["sauvegarde"], ["rapport.txt"])),
            ("b", "cp rapport.txt sauvegarde/",
             _apres(["rapport.txt", "sauvegarde"], ["rapport.txt"])),
            ("c", "cp rapport.txt sauvegarde/rapport.bak",
             _apres(["rapport.txt", "sauvegarde"], ["rapport.bak"])),
            ("d", "mv rapport.txt rapport.bak",
             _apres(["rapport.bak", "sauvegarde"], [])),
        )),
    },
    ref={"cmd": "a"},
    rows=lambda p, get: get("cmd")(p),
    level=2,
)


# --------------------------------------------------------------------------
# Ajouter à la suite
# --------------------------------------------------------------------------

def _redirection(p):
    nom, mot1, mot2 = REDIRECTIONS[p["g"]]
    return {"nom": nom, "mot1": mot1, "mot2": mot2}


AJOUTER = Pattern(
    key="lx_ajouter",
    name="Ajouter à la suite d'un fichier",
    brief="Écrire le second mot dans le fichier sans effacer le premier.",
    why="Rediriger, c'est choisir entre repartir de zéro et continuer.",
    lesson=lecon(
        "`>` envoie la sortie dans un fichier, qu'il **vide d'abord**.",
        "`>>` l'ajoute **à la suite** de ce qui s'y trouve déjà.",
        "`<` fait l'inverse : il donne le fichier à lire à la commande. "
        "`echo`, lui, ne lit rien du tout — il affiche ses arguments.",
        "`tee` écrit à la fois dans le fichier et à l'écran ; `-a` lui dit "
        "d'ajouter plutôt que d'écraser.",
    ),
    dims=(("g", 0, 3),),
    derive=_redirection,
    tpl="""$ echo "@mot1@" > @nom@
$ echo "@mot2@" @op@ @nom@
$ cat @nom@""",
    blanks={
        "op": ("Ce qui relie la commande au fichier", _opts(
            ("a", ">>", lambda p: [p["mot1"], p["mot2"]]),
            ("b", ">", lambda p: [p["mot2"]]),
            ("c", "<", lambda p: [p["mot2"], p["mot1"]]),
            ("d", "| tee -a",
             lambda p: [p["mot2"], p["mot1"], p["mot2"]]),
        )),
    },
    ref={"op": "a"},
    rows=lambda p, get: get("op")(p),
    level=2,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

def _semaine(p):
    mots = list(SEMAINES[p["g"]][:p["n"]])
    return {"mots": mots, "ligne": " ".join(mots)}


BUG_ECRASEMENT = debug_pattern(
    key="lx_bug_ecrasement",
    name="Bug : la liste écrite dans un fichier",
    but="écrire chaque mot de la liste dans jours.txt, un par ligne",
    defaut="> au lieu de >> : le fichier est vidé à chaque tour",
    dims=(("g", 0, 3), ("n", 3, 5)),
    derive=_semaine,
    tpl="""#!/bin/bash
for mot in @ligne@; do
    echo "$mot" > jours.txt
done
cat jours.txt""",
    attendu=lambda p: p["mots"],
    obtenu=lambda p: p["mots"][-1:],
    diagnostics=(
        ("a", "`>` vide le fichier avant d'écrire : chaque tour efface le "
              "précédent. Il faudrait `>>`.",
         "Exact. `>` ouvre le fichier en écriture et le tronque, à chaque "
         "tour. Seul le dernier mot survit. `>>` ouvre en ajout : c'est ce "
         "qu'il faut ici."),
        ("b", "La boucle ne fait qu'un seul tour.",
         "Non : la boucle parcourt bien tous les mots. Remplacez `>` par "
         "`>>` sans rien changer d'autre, et les lignes seront toutes là."),
        ("c", "`cat` n'affiche que la dernière ligne d'un fichier.",
         "Non : `cat` affiche le fichier entier. S'il ne montre qu'une "
         "ligne, c'est que le fichier n'en contient qu'une."),
        ("d", "Il manque des guillemets autour de `$mot`.",
         "Non : les guillemets sont là, et aucun de ces mots ne contient "
         "d'espace. Le nombre de lignes écrites est le vrai problème."),
    ),
    bonne="a",
    level=2,
)


# --------------------------------------------------------------------------
# Prédiction
# --------------------------------------------------------------------------

PREDIRE_RANGER = predict_from(
    RANGER,
    key="lx_predire_ranger",
    name="Prédire : le dossier après un mv",
    why="Deux dossiers à tenir à jour, et un fichier qui passe de l'un à l'autre.",
    level=3,
    output_format=(
        ".:",
        "<entrée>",
        "…",
        "",
        "sauvegarde:",
        "<entrée>",
        "…",
    ),
    dims=(("g", 0, 3), ("n", 1, 2)),
    lesson=predire(RANGER),
)


PATTERNS = (CACHES, UN_PAR_LIGNE, PARENT, COMPTER, FIN_JOURNAL, RANGER, AJOUTER,
            BUG_ECRASEMENT, PREDIRE_RANGER)

MODULE = Module(
    key="linux_fichiers",
    title="Fichiers et dossiers",
    level=1,
    summary="Se repérer avec pwd et cd, lister avec ls -1 et ls -l, "
            "compter avec wc, "
            "copier, déplacer, et rediriger une sortie dans un fichier.",
    keys=tuple(p.key for p in PATTERNS),
)
