#!/usr/bin/env python3
"""Confronte les sorties simulées du chapitre Linux au vrai shell.

Chaque exercice de Linux reconstitue en Python ce qu'affiche une
commande. Si la simulation dérive, l'exercice enseigne une chose fausse
— et l'élève le découvrira dans son terminal, pas ici. Cet outil rejoue
donc chaque exercice pour de bon : il monte le décor dans un dossier
temporaire, lance la commande de chaque option, et compare sa sortie à
celle que l'application annonce. Tous les tirages, toutes les options.

    python3 outils/verif_linux.py

Il n'est pas dans la suite de tests : il exige un shell GNU (coreutils,
findutils, sed, awk) et une locale stable, ce qu'on ne peut pas
supposer d'une machine de passage. Les valeurs qu'il a validées sont
recopiées à la main dans `LinuxTest`, qui, lui, tourne partout.

Deux exercices échappent à ce contrôle : `lx_parent`, dont la sortie est
un chemin absolu qu'aucune machine d'essai ne peut reproduire, et la
colonne propriétaire/taille/date de `ls -l`, que les exercices de droits
inventent. Seule la colonne des droits y est comparée.
"""

import itertools, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
from atelier import exercises as ex

def run(script, cwd):
    r = subprocess.run(["bash", "-c", script], cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, env=dict(os.environ, LC_ALL=""))
    out = r.stdout
    return [l for l in out.split("\n")[:-1]] if out else []

def draws(pattern):
    specs = ex.specs(pattern)
    noms = [n for n, _a, _b in specs]
    for combo in itertools.product(*[range(a, b + 1) for _n, a, b in specs]):
        p = dict(zip(noms, combo))
        if pattern.derive:
            p.update(pattern.derive(p))
        yield p

def ecrire(d, nom, lignes):
    with open(os.path.join(d, nom), "w") as fh:
        fh.write("\n".join(lignes) + "\n")

ECHECS = []

def compare(cle, p, choix, attendu, obtenu):
    if attendu != obtenu:
        ECHECS.append((cle, choix, p.get("g"), p.get("n"), p.get("d"),
                       attendu, obtenu))

def verifie(cle, prepare, commande):
    """prepare(d, p) construit le decor ; commande(p, texte) rend le script."""
    pattern = ex.PATTERNS[cle]
    blank = list(pattern.blanks)[0]
    for p in draws(pattern):
        for opt in pattern.blanks[blank][1]:
            d = tempfile.mkdtemp()
            try:
                prepare(d, p)
                reel = run(commande(p, opt.c), d)
                simule = ex.build_rows(cle, p, {blank: opt.id})
                compare(cle, p, opt.c, [l.rstrip() for l in reel],
                        [l.rstrip() for l in simule])
            finally:
                shutil.rmtree(d)
    print("verifie", cle)

def verifie_debug(cle, prepare, script):
    pattern = ex.PATTERNS[cle]
    for p in draws(pattern):
        d = tempfile.mkdtemp()
        try:
            prepare(d, p)
            reel = run(script(p), d)
            compare(cle, p, "(obtenu)", [l.rstrip() for l in reel],
                    [l.rstrip() for l in ex.broken_rows(cle, p)])
        finally:
            shutil.rmtree(d)
    print("verifie", cle, "(debug)")

# -- module fichiers -------------------------------------------------------

def prep_caches(d, p):
    for nom in p["caches"] + p["visibles"]:
        open(os.path.join(d, nom), "w").close()
verifie("lx_caches", prep_caches, lambda p, c: c)

def prep_texte(d, p):
    ecrire(d, p["nom"], p["lignes"])
verifie("lx_compter", prep_texte, lambda p, c: "wc %s %s" % (c, p["nom"]))
verifie("lx_fin_journal", prep_texte, lambda p, c: "%s %s" % (c, p["nom"]))

def prep_ranger(d, p):
    os.mkdir(os.path.join(d, "sauvegarde"))
    for nom in ["rapport.txt"] + p["voisins"]:
        open(os.path.join(d, nom), "w").close()
verifie("lx_ranger", prep_ranger,
        lambda p, c: "%s; ls -1 . sauvegarde" % c)

verifie("lx_ajouter", lambda d, p: None,
        lambda p, c: 'echo "%s" > %s; echo "%s" %s %s; cat %s'
        % (p["mot1"], p["nom"], p["mot2"], c, p["nom"], p["nom"]))

verifie_debug("lx_bug_ecrasement", lambda d, p: None,
              lambda p: 'for mot in %s; do echo "$mot" > jours.txt; done; '
                        'cat jours.txt' % p["ligne"])

# -- module filtres --------------------------------------------------------

verifie("lx_chercher", prep_texte,
        lambda p, c: "%s erreur %s" % (c, p["nom"]))
verifie("lx_colonne", prep_texte, lambda p, c: "cut %s %s" % (c, p["nom"]))

def prep_nombres(d, p):
    ecrire(d, "nombres.txt", p["lignes"])
verifie("lx_trier", prep_nombres, lambda p, c: c)

def prep_liste(d, p):
    ecrire(d, "liste.txt", p["lignes"])
verifie("lx_dedoublonner", prep_liste, lambda p, c: c)

def prep_acces(d, p):
    ecrire(d, "acces.log", p["lignes"])
verifie("lx_palmares", prep_acces, lambda p, c: c)

verifie_debug("lx_bug_uniq", prep_liste, lambda p: "uniq liste.txt")

# -- module droits ---------------------------------------------------------

def prep_arbre(d, p):
    for chemin in p["chemins"]:
        plein = os.path.join(d, chemin)
        if chemin in p["dossiers"]:
            os.makedirs(plein, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(plein), exist_ok=True)
            open(plein, "w").close()
verifie("lx_trouver", prep_arbre, lambda p, c: "find . %s | sort" % c)
verifie("lx_menage", prep_arbre, lambda p, c: "%s; find . | sort" % c)

# chmod : seule la colonne des droits est reproductible d'une machine a
# l'autre (proprietaire, taille et date sont inventes par l'exercice).
def verifie_chmod(cle, depart):
    pattern = ex.PATTERNS[cle]
    blank = list(pattern.blanks)[0]
    for p in draws(pattern):
        for opt in pattern.blanks[blank][1]:
            d = tempfile.mkdtemp()
            try:
                open(os.path.join(d, p["nom"]), "w").close()
                reel = run("chmod %s %s; chmod %s %s; ls -l %s | cut -d' ' -f1"
                           % (depart(p), p["nom"], opt.c, p["nom"], p["nom"]), d)
                simule = ex.build_rows(cle, p, {blank: opt.id})[0].split(" ")[0]
                compare(cle, p, opt.c, reel, [simule])
            finally:
                shutil.rmtree(d)
    print("verifie", cle, "(droits seuls)")

verifie_chmod("lx_chmod_octal", lambda p: "644")
verifie_chmod("lx_chmod_symbolique", lambda p: p["mode"])

def prep_chmod_bug(d, p):
    with open(os.path.join(d, "essai.sh"), "w") as fh:
        fh.write(ex.render_code("lx_bug_chmod", p) + "\n")
verifie_debug("lx_bug_chmod", prep_chmod_bug, lambda p: "bash essai.sh")

# -- module shell ----------------------------------------------------------

def prep_args(d, p):
    ecrire(d, "infos.sh", ["#!/bin/bash"])
verifie("lx_args", prep_args,
        lambda p, c: "printf '#!/bin/bash\\necho %s\\n' > infos.sh; "
                     "chmod +x infos.sh; ./infos.sh %s"
                     % (c.replace("'", "'\\''"), p["ligne"]))

def prep_rapport(d, p):
    ecrire(d, "rapport.txt", p["lignes"])
verifie("lx_enchainer", prep_rapport, lambda p, c: c)

verifie("lx_remplacer", prep_texte, lambda p, c: "%s %s" % (c, p["nom"]))
verifie("lx_total", prep_texte, lambda p, c: "awk %s %s" % (c, p["nom"]))

def prep_glob(d, p):
    for nom in p["fichiers"]:
        open(os.path.join(d, nom), "w").close()
verifie("lx_pour_chaque", prep_glob,
        lambda p, c: 'for f in %s; do echo "-- $f"; done' % c)

verifie_debug("lx_bug_guillemets", lambda d, p: None,
              lambda p: 'cat > "%s" <<EOF\n%s\nEOF\nfichier="%s"\nwc -l $fichier'
                        % (p["nom"], p["contenu"], p["nom"]))

print()
if ECHECS:
    print("ECHECS :", len(ECHECS))
    for cle, choix, g, n, dd, reel, simule in ECHECS[:40]:
        print("---", cle, "option", repr(choix), "g=%s n=%s d=%s" % (g, n, dd))
        print("  reel   :", reel)
        print("  simule :", simule)
else:
    print("Tout concorde.")
sys.exit(1 if ECHECS else 0)
