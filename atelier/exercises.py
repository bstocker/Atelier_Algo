"""Catalogue des exercices : chapitres, modules, et registre.

Le socle du moteur est dans `atelier/engine.py`, les exercices dans
`atelier/modules/`. Ce fichier ne fait que les assembler, et reste le
point d'entrée unique du reste de l'application.

Ajouter un module tient en trois gestes : un fichier dans
`atelier/modules/`, son import ici, et son entrée dans un chapitre.

Le chapitre QCM a ceci de particulier qu'il accueille aussi des modules
**importés** : un classeur Excel déposé par l'enseignant devient un
sous-module, rangé dans la base et non dans le code. `refresh()` les
recharge ; tout le reste du catalogue est figé au démarrage.
"""

from .engine import (  # noqa: F401  — réexportés pour le reste de l'appli
    BLANK_PLACEHOLDER, CHOICE_LETTERS, LEVELS, PREDICT_CHOICES, QCM_CHOICES,
    Chapter, InfiniteLoop, Module, Option, Pattern, PATTERNS, answer_space,
    broken_rows, build_rows, build_trace, code_template, compare,
    debug_pattern, draw_params, option_note, predict_from, qcm_pattern,
    register, render_code, shuffled_blanks, specs, substitute, target_rows,
    unregister,
)
from .modules import (arguments, boucles, chaines, conditions, linux_droits,
                      linux_fichiers, linux_filtres, linux_shell, qcm_docker,
                      recursif, reseau_masques, tableaux)

# Chapitres livrés avec l'application. Le chapitre QCM reçoit en plus, à
# l'exécution, les modules importés depuis la console (cf. `refresh`).
BASE_CHAPTERS = (
    Chapter(
        key="c",
        title="Langage C",
        summary="Les bases du C, module par module.",
        modules=(boucles.MODULE, conditions.MODULE, chaines.MODULE,
                 tableaux.MODULE, recursif.MODULE,
                 arguments.MODULE),
    ),
    Chapter(
        key="linux",
        title="Ligne de commande Linux",
        summary="Les commandes du terminal, module par module.",
        modules=(linux_fichiers.MODULE, linux_filtres.MODULE,
                 linux_droits.MODULE, linux_shell.MODULE),
        action="Exécuter la commande",
    ),
    Chapter(
        key="reseau",
        title="Réseau",
        summary="L'adressage IP, module par module.",
        modules=(reseau_masques.MODULE,),
        action="Lancer le calcul",
    ),
    Chapter(
        key="qcm",
        title="QCM",
        summary="Des questionnaires à choix unique : une question, quatre "
                "propositions, une seule juste. Importables au format Excel.",
        modules=(qcm_docker.MODULE,),
    ),
)

QCM_CHAPTER_KEY = "qcm"

for _module in (boucles, conditions, chaines, tableaux, recursif,
                arguments, linux_fichiers, linux_filtres, linux_droits,
                linux_shell, reseau_masques, qcm_docker):
    register(_module.PATTERNS)

# Modules importés actuellement chargés : clé -> Module. Reconstruits par
# `refresh()`, qui seul a le droit d'y toucher.
_IMPORTED = {}

# Remplis par `_rebuild()`, juste en dessous. Le reste de l'application les
# lit par attribut (`ex.MODULES`), donc les voit changer après un import.
CHAPTERS = ()
MODULES = ()
CHAPTER_OF = {}
MODULE_BY_KEY = {}
ALL_KEYS = []
_MODULE_OF = {}


def _rebuild():
    """Recalcule les index du catalogue à partir des modules chargés."""
    global CHAPTERS, MODULES, CHAPTER_OF, MODULE_BY_KEY, ALL_KEYS, _MODULE_OF
    CHAPTERS = tuple(
        Chapter(key=c.key, title=c.title, summary=c.summary,
                modules=c.modules + tuple(_IMPORTED.values()),
                action=c.action)
        if c.key == QCM_CHAPTER_KEY else c
        for c in BASE_CHAPTERS
    )
    MODULES = tuple(m for chapter in CHAPTERS for m in chapter.modules)
    CHAPTER_OF = {m.key: c for c in CHAPTERS for m in c.modules}
    MODULE_BY_KEY = {m.key: m for m in MODULES}
    ALL_KEYS = [key for module in MODULES for key in module.keys]
    _MODULE_OF = {key: m for m in MODULES for key in m.keys}


_rebuild()


def refresh(modules):
    """Remplace les modules importés du chapitre QCM.

    `modules` est une liste de `(Module, [Pattern])`, dans l'ordre où
    l'enseignant les a importés. Les anciens sont retirés du registre
    avant que les nouveaux n'y entrent : un module réimporté ne doit pas
    buter sur ses propres clés.
    """
    for module in _IMPORTED.values():
        unregister(module.keys)
    _IMPORTED.clear()
    for module, patterns in modules:
        _IMPORTED[module.key] = module
        register(patterns)
    _rebuild()


def module_of(pattern_key):
    """Module auquel appartient un exercice."""
    return _MODULE_OF[pattern_key]


def chapter_of(pattern_key):
    """Chapitre auquel appartient un exercice."""
    return CHAPTER_OF[module_of(pattern_key).key]


def modules_for(pattern_keys):
    """Modules couverts par une liste d'exercices, dans l'ordre du catalogue.

    Sert à n'afficher les intitulés de module que lorsqu'une session en
    croise plusieurs : avec un seul, ils n'apporteraient que du bruit.
    """
    present = {module_of(k).key for k in pattern_keys}
    return [m for m in MODULES if m.key in present]


def catalogue():
    """Le catalogue tel que l'enseignant le compose.

    Rend une liste de (chapitre, [(module, [(niveau, libellé, exercices)])]).
    """
    out = []
    for chapter in CHAPTERS:
        modules = []
        for module in chapter.modules:
            niveaux = []
            for level in sorted(LEVELS):
                motifs = [PATTERNS[k] for k in module.keys
                          if PATTERNS[k].level == level]
                if motifs:
                    niveaux.append((level, LEVELS[level], motifs))
            modules.append((module, niveaux))
        out.append((chapter, modules))
    return out
