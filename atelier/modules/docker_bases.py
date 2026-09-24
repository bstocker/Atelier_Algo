"""Module « Les conteneurs : premiers pas », du chapitre Docker.

Des questions de cours, et rien au-delà de la première séance : lancer
une image en arrière-plan et publier son port, lister, arrêter, relancer
et supprimer un conteneur, le nommer, et trouver une image sur Docker
Hub. Les images sont celles de la séance — le serveur httpd de quay.io,
Tetris et Mario sur Docker Hub.

Chaque affirmation d'une bonne réponse a été rejouée sur un vrai démon
Docker : le port déjà alloué, le nom déjà pris, le `rm` refusé sur un
conteneur qui tourne, le conteneur arrêté qui reste dans `docker ps -a`.
"""

from ..engine import Module, qcm_pattern
from .qcm_docker import _tourner

# Les images vues en séance.
HTTPD = "quay.io/ocp-edge-qe/httpd"

# (énoncé, (quatre propositions), index de la bonne, niveau, explication)
# Comme dans qcm_docker, la bonne réponse est écrite en premier puis
# déplacée par `_tourner`.
QUESTIONS = (
    ("Que fait l'option `-d` dans `docker run -d -p 80:80 %s` ?" % HTTPD,
     ("Elle lance le conteneur en arrière-plan et rend la main au terminal",
      "Elle supprime le conteneur dès qu'il s'arrête",
      "Elle télécharge l'image sans lancer de conteneur",
      "Elle donne un nom au conteneur"),
     0, 1,
     "`-d` pour *detached* : Docker affiche l'identifiant du conteneur et "
     "rend le terminal tout de suite, pendant que le serveur tourne."),

    ("Dans `docker run -d -p 81:80 %s`, que désigne le **81** ?" % HTTPD,
     ("Le port de la machine hôte, celui qu'on ouvre dans le navigateur",
      "Le port sur lequel le serveur écoute à l'intérieur du conteneur",
      "Le nombre de conteneurs lancés",
      "La version de l'image httpd"),
     0, 2,
     "`-p` se lit toujours **hôte:conteneur**. Le 81 est le port de la "
     "machine ; le 80, celui du serveur dans le conteneur."),

    ("On a lancé `docker run -d -p 80:80 %s`, puis "
     "`docker run -d -p 81:80 %s`. Quelle adresse mène au **second** "
     "serveur ?" % (HTTPD, HTTPD),
     ("http://localhost:81",
      "http://localhost:80",
      "http://localhost:8081",
      "Aucune : deux conteneurs ne peuvent pas tourner ensemble"),
     0, 2,
     "Le second conteneur publie le port 80 de son serveur sur le port 81 "
     "de la machine. Les deux serveurs tournent côte à côte, chacun "
     "derrière son port."),

    ("Pourquoi le second serveur httpd a-t-il été lancé avec `-p 81:80`, "
     "et non `-p 80:80` comme le premier ?",
     ("Le port 80 de la machine était déjà pris par le premier conteneur",
      "L'image httpd n'accepte qu'un seul lancement avec le port 80",
      "Le port 80 est réservé à Docker Hub",
      "Le second conteneur doit écouter sur le port 81 à l'intérieur"),
     0, 3,
     "Un port de la machine ne peut être publié qu'une fois. Relancer "
     "`-p 80:80` échoue avec « port is already allocated ». À "
     "l'intérieur, chaque conteneur a son propre port 80 : pas de "
     "conflit de ce côté-là."),

    ("Quelle commande liste **tous** les conteneurs, y compris ceux qui "
     "sont arrêtés ?",
     ("docker ps -a",
      "docker ps",
      "docker list",
      "docker images"),
     0, 1,
     "`docker ps` seul ne montre que les conteneurs qui tournent. `-a` "
     "(*all*) ajoute ceux qui sont arrêtés."),

    ("Où trouve-t-on le CONTAINER_ID à donner à `docker stop`, "
     "`docker start` ou `docker rm` ?",
     ("Dans la première colonne de `docker ps -a`",
      "Sur la page de l'image, sur Docker Hub",
      "Dans le nom de l'image, après la barre oblique",
      "Il faut le choisir soi-même avant de lancer le conteneur"),
     0, 1,
     "Docker attribue l'identifiant au lancement. `docker ps -a` l'affiche "
     "dans sa colonne CONTAINER ID ; les premiers caractères suffisent."),

    ("Quelle commande arrête un conteneur qui tourne ?",
     ("docker stop CONTAINER_ID",
      "docker rm CONTAINER_ID",
      "docker ps -a",
      "docker end CONTAINER_ID"),
     0, 1,
     "`docker stop` arrête le conteneur sans le supprimer."),

    ("Après un `docker stop`, le conteneur apparaît-il encore dans "
     "`docker ps -a` ?",
     ("Oui, avec un état `Exited`, jusqu'à ce qu'on le supprime",
      "Non, `docker stop` le supprime",
      "Oui, mais avec un nouvel identifiant",
      "Non, il n'apparaît plus que dans `docker ps`"),
     0, 2,
     "Arrêter n'est pas supprimer. Le conteneur reste là, arrêté : "
     "`docker ps` ne le montre plus, `docker ps -a` si."),

    ("Quelle commande relance un conteneur arrêté ?",
     ("docker start CONTAINER_ID",
      "docker run CONTAINER_ID",
      "docker ps CONTAINER_ID",
      "docker up CONTAINER_ID"),
     0, 1,
     "`docker start` relance le conteneur existant, avec le même "
     "identifiant. `docker run`, lui, crée un conteneur neuf à partir "
     "d'une image."),

    ("Quelle commande supprime un conteneur ?",
     ("docker rm CONTAINER_ID",
      "docker stop CONTAINER_ID",
      "docker delete CONTAINER_ID",
      "docker ps -rm CONTAINER_ID"),
     0, 1,
     "`rm` pour *remove*. Une fois supprimé, le conteneur disparaît aussi "
     "de `docker ps -a`."),

    ("Que se passe-t-il si l'on fait `docker rm` sur un conteneur qui "
     "tourne encore ?",
     ("Docker refuse : il faut d'abord l'arrêter avec `docker stop`",
      "Docker l'arrête puis le supprime, sans rien demander",
      "Docker supprime l'image dont il est issu",
      "Le conteneur est supprimé mais le serveur continue de répondre"),
     0, 3,
     "Docker répond « container is running: stop the container before "
     "removing ». D'où l'ordre vu en séance : `docker stop`, puis "
     "`docker rm`."),

    ("Qu'est-ce que Docker Hub ?",
     ("Un store où les utilisateurs de Docker partagent leurs images",
      "Le programme qui fait tourner les conteneurs sur la machine",
      "La commande qui liste les conteneurs",
      "Un conteneur qui héberge tous les autres"),
     0, 1,
     "Docker Hub (hub.docker.com) est un catalogue d'images : on y "
     "cherche une image, puis `docker run` la télécharge et la lance."),

    ("Sur Docker Hub, qui a créé les images de base ?",
     ("L'équipe de Docker",
      "Chaque utilisateur, lors de son premier `docker run`",
      "Les éditeurs de navigateurs web",
      "Personne : elles sont générées automatiquement"),
     0, 2,
     "Les images de base sont maintenues par l'équipe de Docker ; les "
     "autres sont partagées par les utilisateurs, comme `bsord/tetris`."),

    ("Dans `docker run -d -p 80:80 --name tetris bsord/tetris`, "
     "que désigne `bsord` ?",
     ("Le compte Docker Hub de l'utilisateur qui a publié l'image",
      "Le nom donné au conteneur",
      "Le port publié sur la machine",
      "La version de l'image tetris"),
     0, 2,
     "Une image partagée s'écrit **compte/image** : `bsord/tetris` est "
     "l'image tetris publiée par l'utilisateur bsord. Le nom du conteneur, "
     "lui, vient de `--name`."),

    ("À quoi sert `--name tetris` dans "
     "`docker run -d -p 80:80 --name tetris bsord/tetris` ?",
     ("À nommer le conteneur, pour écrire `docker stop tetris` au lieu "
      "de son identifiant",
      "À choisir l'image à télécharger sur Docker Hub",
      "À donner son titre à la page du jeu",
      "À publier le port 80 sous le nom tetris"),
     0, 2,
     "Sans `--name`, Docker invente un nom au hasard. Avec, le nom "
     "remplace l'identifiant dans `docker stop`, `docker start` et "
     "`docker rm`."),

    ("Dans `docker run -d -p 80:80 %s`, d'où vient l'image ?" % HTTPD,
     ("Du registre quay.io, un autre store d'images que Docker Hub",
      "De Docker Hub, comme toutes les images",
      "D'un fichier httpd présent dans le dossier courant",
      "D'un site web à ouvrir sur le port 80"),
     0, 3,
     "Le début du nom désigne le registre. Sans lui, comme dans "
     "`bsord/tetris`, Docker va chercher sur Docker Hub."),

    ("Tetris tourne déjà, lancé par "
     "`docker run -d -p 80:80 --name tetris bsord/tetris`. "
     "Quelle commande met Mario en ligne **à côté** ?",
     ("docker run -d -p 81:80 --name mario sevenajay/mario",
      "docker run -d -p 80:80 --name mario sevenajay/mario",
      "docker run -d -p 81:80 --name tetris sevenajay/mario",
      "docker run -d -p 80:81 --name mario sevenajay/mario"),
     0, 4,
     "Il faut un port de la machine libre **et** un nom libre. Le port 80 "
     "est pris par Tetris (« port is already allocated »), le nom tetris "
     "aussi (« name is already in use »). `-p 80:81` réclamerait encore "
     "le port 80 de la machine."),
)


def _build(rang, question, choices, answer, level, explanation):
    choices, answer = _tourner(choices, answer, rang)
    return qcm_pattern("dk_bases_%02d" % rang, rang, question,
                       choices, answer, level, explanation)


PATTERNS = tuple(
    _build(number + 1, *entree) for number, entree in enumerate(QUESTIONS)
)

MODULE = Module(
    key="docker_bases",
    title="Les conteneurs : premiers pas",
    level=1,
    summary="Lancer une image avec docker run -d -p, lister, arrêter, "
            "relancer et supprimer un conteneur, le nommer, et trouver une "
            "image sur Docker Hub.",
    keys=tuple(p.key for p in PATTERNS),
)
