"""Ce que les modules du chapitre Linux ont en commun.

Un exercice de C montre un programme ; un exercice de Linux montre une
**session de terminal** : les lignes préfixées par `$` sont les commandes
tapées, les autres ce qu'elles ont affiché. La dernière commande porte le
trou, et la cible est ce qu'elle imprime — le reste de la session sert de
contexte, exactement comme les `printf` d'un gabarit de C.

Les sorties sont écrites telles que les rendent les outils GNU : c'est
l'intérêt de l'exercice, et un élève qui compare à son terminal doit
retrouver le même texte au caractère près.
"""

# Rappel porté par tous les exercices du chapitre : sans lui, un élève qui
# tombe sur un seul exercice ne sait pas lire le bloc.
SESSION = ("Le bloc ci-dessous est une **session de terminal** : les lignes "
           "qui commencent par `$` sont les commandes tapées, les autres ce "
           "qu'elles ont affiché. La sortie à reproduire est celle de la "
           "**dernière** commande.",)


def lecon(*points):
    """Rappel de cours d'un exercice Linux : la convention, puis le fond."""
    return SESSION + points


def predire(base):
    """Rappel d'une prédiction tirée de `base`.

    Le rappel par défaut de `predict_from` parle de boucles C. Ici, la
    convention de lecture change — la dernière commande n'affiche rien,
    c'est à l'élève de l'écrire — mais le fond reste celui de l'exercice
    d'origine : pour prédire `cut`, il faut savoir ce que fait `cut`.
    """
    return (
        "Le bloc ci-dessous est une **session de terminal** : les lignes "
        "qui commencent par `$` sont les commandes tapées, les autres ce "
        "qu'elles ont affiché. La **dernière** commande n'a encore rien "
        "affiché : c'est sa sortie que vous écrivez.",
        "Ne devinez pas : **rejouez** les commandes dans l'ordre, en "
        "partant de ce que les précédentes ont affiché.",
    ) + tuple(base.lesson[len(SESSION):]) + (
        "Les espaces comptent. Une ligne décalée d'un espace est fausse.",
        "Les espaces en fin de ligne, eux, sont ignorés.",
    )


def trier(noms):
    """Ordonne des noms comme `ls` le fait.

    `ls` trie selon la locale, qui ignore le point de tête : `.config`
    vient avant `notes.txt` mais après `bilan.md`. Les jeux de ce chapitre
    sont choisis pour que cet ordre coïncide avec celui de la locale C,
    afin qu'un élève retrouve la même sortie sur n'importe quelle machine.
    """
    return sorted(noms, key=lambda nom: nom.lstrip("."))


def listing(racine, dossier, entrees):
    """Sortie de `ls -1 . <dossier>`, deux dossiers en une commande.

    `ls` annonce alors chaque dossier par son nom suivi de deux points, et
    les sépare par une ligne vide. Un dossier vide n'ajoute rien après son
    intitulé.
    """
    return ([".:"] + trier(racine) + ["", "%s:" % dossier]
            + trier(entrees))


def compte(nombre, texte):
    """Une ligne de `uniq -c` : le compte aligné sur sept colonnes."""
    return "%7d %s" % (nombre, texte)


def paquets(lignes):
    """Groupes de lignes identiques **consécutives**, comme les voit `uniq`.

    C'est toute la subtilité de `uniq` : il ne compare qu'à la ligne
    précédente. Deux occurrences séparées par une autre valeur comptent
    pour deux groupes, d'où le `sort` qui le précède presque toujours.
    """
    groupes = []
    for ligne in lignes:
        if groupes and groupes[-1][1] == ligne:
            groupes[-1][0] += 1
        else:
            groupes.append([1, ligne])
    return [(nombre, ligne) for nombre, ligne in groupes]
