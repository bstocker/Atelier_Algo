#!/usr/bin/env python3
"""Dit où vit la base, sous quel mode de journalisation, et sur quel disque.

À lancer dans une console de l'hébergeur, depuis le dossier de
l'application :

    python3 outils/diag_base.py

Trois questions, une réponse chacune.

**Quel mode de journalisation ?** `schema.sql` demande `journal_mode =
WAL`, et `init_db()` rejoue ce fichier à chaque démarrage de processus.
Or le mode WAL exige de la mémoire partagée entre les processus qui
ouvrent la base — ce qu'un disque monté par le réseau ne fournit pas.
SQLite le documente, et des utilisateurs de PythonAnywhere y ont perdu
des bases. Si la base est sur un disque réseau, ce mode est à quitter.

**Sur quel disque ?** La réponse vient de `/proc/mounts` : `ext4` ou
`overlay` sont locaux, tout ce qui ressemble à `nfs` ne l'est pas.

**Et les fichiers annexes ?** Un `-wal` et un `-shm` à côté de la base
confirment que le mode WAL est bien actif, et pas seulement demandé.

L'outil n'ouvre la base **qu'en lecture** : il ne peut donc pas changer
le mode qu'il vient mesurer — ce que ferait, lui, un simple démarrage de
l'application.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atelier import load_env_file          # noqa: E402


def chemin_base():
    """Le même chemin que celui que `create_app()` retiendrait.

    On ne passe surtout pas par `create_app()` : il appelle `init_db()`,
    qui rejoue `schema.sql`, donc repose le mode WAL. L'outil mesurerait
    alors ce qu'il vient lui-même d'écrire.
    """
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_env_file(os.environ.get("ATELIER_ENV_FILE",
                                 os.path.join(racine, ".env")))
    return os.environ.get("ATELIER_DATABASE",
                          os.path.join(racine, "instance", "atelier.sqlite"))


def systeme_de_fichiers(chemin):
    """Type du système de fichiers qui porte ce chemin, selon /proc/mounts."""
    try:
        with open("/proc/mounts", encoding="utf-8") as fh:
            montages = [ligne.split()[1:3] for ligne in fh]
    except OSError:
        return "inconnu"
    chemin = os.path.abspath(chemin)
    retenu = ("/", "inconnu")
    for point, type_fs in montages:
        if chemin == point or chemin.startswith(point.rstrip("/") + "/"):
            if len(point) >= len(retenu[0]):
                retenu = (point, type_fs)
    return retenu[1]


def main():
    base = chemin_base()
    print("Base        : %s" % base)
    if not os.path.isfile(base):
        print("            ! aucun fichier à cet endroit")
        return 1

    taille = os.path.getsize(base) / 1024.0
    fs = systeme_de_fichiers(base)
    reseau = any(marque in fs for marque in ("nfs", "cifs", "smb", "fuse"))
    print("Taille      : %.0f Kio" % taille)
    print("Disque      : %s%s" % (fs, "  ← monté par le réseau" if reseau
                                  else "  (local)"))

    annexes = [suffixe for suffixe in ("-wal", "-shm")
               if os.path.exists(base + suffixe)]
    print("Fichiers    : %s" % (", ".join(annexes) if annexes
                                else "aucun -wal ni -shm"))

    try:
        conn = sqlite3.connect("file:%s?mode=ro" % base, uri=True)
    except sqlite3.Error as erreur:
        print("Journal     : illisible (%s)" % erreur)
        return 1
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        integre = conn.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        conn.close()
    print("Journal     : %s" % mode)
    print("Intégrité   : %s" % integre)

    print()
    if mode.lower() == "wal" and reseau:
        print("À CORRIGER. Le mode WAL sur un disque réseau n'est pas")
        print("supporté par SQLite et expose la base à la corruption.")
        print("Remplacer le PRAGMA de schema.sql par journal_mode = DELETE,")
        print("puis rejouer la bascule une fois sur la base en place.")
    elif mode.lower() == "wal":
        print("Le mode WAL est actif, sur un disque local : rien à signaler.")
    else:
        print("Mode de journalisation sans risque sur ce disque.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
