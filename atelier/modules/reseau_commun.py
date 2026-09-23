"""Ce que les modules du chapitre Réseau ont en commun.

Un exercice de C montre un programme, un exercice de Linux une session de
terminal ; un exercice de réseau montre une **fiche de calcul** : les
lignes `nom : valeur` sont les données, les lignes `nom = …` disent ce
qu'on en tire. Le trou est dans la fiche, et la cible est le résultat
des calculs — exactement comme les `printf` d'un gabarit de C.

Les calculs sont faits ici à la main, bit à bit, comme l'élève les fait
sur papier. `ReseauTest` les confronte au module `ipaddress` de la
bibliothèque standard, pour chaque tirage : une fiche qui annoncerait un
faux réseau enseignerait une chose fausse.
"""

# Rappel porté par tous les exercices du chapitre : sans lui, un élève qui
# tombe sur un seul exercice ne sait pas lire le bloc.
FICHE = ("Le bloc ci-dessous est une **fiche de calcul** : les lignes "
         "`nom : valeur` sont les données, les lignes `nom = …` disent ce "
         "qu'on calcule. La sortie à reproduire est le **résultat** de ces "
         "calculs.",)


def lecon(*points):
    """Rappel de cours d'un exercice de réseau : la convention, puis le fond."""
    return FICHE + points


def entier(adresse):
    """`192.168.1.37` -> l'entier de 32 bits qu'elle écrit."""
    valeur = 0
    for octet in adresse.split("."):
        valeur = valeur * 256 + int(octet)
    return valeur


def pointee(valeur):
    """L'inverse : un entier de 32 bits, en notation décimale pointée."""
    return ".".join(str((valeur >> decalage) & 255)
                    for decalage in (24, 16, 8, 0))


def masque(prefixe):
    """Le masque d'un préfixe : `prefixe` bits à 1, puis des 0."""
    return (0xFFFFFFFF << (32 - prefixe)) & 0xFFFFFFFF


def prefixe(masque_pointe):
    """Nombre de bits à 1 d'un masque écrit en décimal pointé."""
    return bin(entier(masque_pointe)).count("1")


def reseau(adresse, masque_pointe):
    """Adresse ET Masque."""
    return pointee(entier(adresse) & entier(masque_pointe))


def diffusion(adresse, masque_pointe):
    """Adresse OU (NON Masque) : tous les bits d'hôte à 1."""
    return pointee(entier(adresse) | (~entier(masque_pointe) & 0xFFFFFFFF))


def hotes(prefixe_):
    """Adresses utilisables : toutes, moins le réseau et la diffusion."""
    return 2 ** (32 - prefixe_) - 2
