"""Catalogue des exercices : chapitres, modules, et registre.

Le socle du moteur est dans `atelier/engine.py`, les exercices dans
`atelier/modules/`. Ce fichier ne fait que les assembler, et reste le
point d'entrée unique du reste de l'application.

Ajouter un module tient en trois gestes : un fichier dans
`atelier/modules/`, son import ici, et son entrée dans un chapitre.
"""

from .engine import (  # noqa: F401  — réexportés pour le reste de l'appli
    BLANK_PLACEHOLDER, LEVELS, PREDICT_CHOICES, Chapter, InfiniteLoop, Module,
    Option, Pattern, PATTERNS, answer_space, broken_rows, build_rows,
    build_trace, code_template, compare, debug_pattern, draw_params,
    option_note, predict_from, register, render_code, shuffled_blanks, specs,
    substitute, target_rows,
)
from .modules import (arguments, boucles, chaines, conditions,
                      recursif, tableaux)

CHAPTERS = (
    Chapter(
        key="c",
        title="Langage C",
        summary="Les bases du C, module par module.",
        modules=(boucles.MODULE, conditions.MODULE, chaines.MODULE,
                 tableaux.MODULE, recursif.MODULE,
                 arguments.MODULE),
    ),
)

MODULES = tuple(m for chapter in CHAPTERS for m in chapter.modules)
CHAPTER_OF = {m.key: c for c in CHAPTERS for m in c.modules}
MODULE_BY_KEY = {m.key: m for m in MODULES}

for _module in (boucles, conditions, chaines, tableaux, recursif,
                arguments):
    register(_module.PATTERNS)

ALL_KEYS = [key for module in MODULES for key in module.keys]

_MODULE_OF = {key: m for m in MODULES for key in m.keys}


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
