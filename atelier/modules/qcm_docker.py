"""Module QCM « Docker : les bases ».

Exemple livré avec l'application : il montre ce qu'un module de QCM
contient, et sert de référence au format d'import Excel — le modèle
téléchargeable depuis la console reprend ces mêmes questions.

Les questions portent sur ce qu'un débutant rencontre en premier : la
différence image / conteneur, les commandes du quotidien, le Dockerfile,
les ports, les volumes. Chaque question a quatre propositions et une seule
réponse juste ; l'explication est montrée après coup, juste ou faux.

Un QCM importé produit exactement la même chose, mais depuis la base.
"""

from ..engine import Module, qcm_pattern

# (énoncé, (quatre propositions), index de la bonne, niveau, explication)
# La bonne réponse est écrite en premier : c'est plus lisible à relire et à
# corriger. Elle est ensuite déplacée (voir `_tourner`), pour que le modèle
# Excel exporté depuis ce module montre les quatre lettres et pas que des A.
QUESTIONS = (
    ("Qu'est-ce qu'une image Docker ?",
     ("Un modèle en lecture seule à partir duquel on lance des conteneurs",
      "Un conteneur en cours d'exécution",
      "Une machine virtuelle complète avec son noyau",
      "Un fichier de configuration du démon Docker"),
     0, 1,
     "L'image est le gabarit figé ; le conteneur en est une instance "
     "vivante. Une même image peut donner cent conteneurs."),

    ("Quelle commande liste les conteneurs en cours d'exécution ?",
     ("docker ps", "docker images", "docker ls", "docker run"),
     0, 1,
     "`docker ps` liste les conteneurs, `docker images` les images. "
     "`docker ps -a` ajoute les conteneurs arrêtés."),

    ("Que fait `docker run nginx` si l'image nginx n'est pas présente ?",
     ("Docker la télécharge depuis le registre, puis lance le conteneur",
      "La commande échoue avec « image not found »",
      "Docker construit l'image à partir du Dockerfile courant",
      "Docker lance un conteneur vide nommé nginx"),
     0, 1,
     "`docker run` fait implicitement un `docker pull` quand l'image "
     "manque en local. C'est ce qui rend le premier lancement plus long."),

    ("Dans un Dockerfile, à quoi sert l'instruction FROM ?",
     ("Elle désigne l'image de base sur laquelle on construit",
      "Elle indique le répertoire source à copier",
      "Elle définit l'utilisateur propriétaire du conteneur",
      "Elle déclare le port exposé par l'application"),
     0, 1,
     "`FROM` est presque toujours la première instruction : elle dit sur "
     "quelle image on empile ses propres couches."),

    ("Quelle est la différence entre COPY et ADD dans un Dockerfile ?",
     ("ADD sait en plus déballer une archive et lire une URL",
      "COPY fonctionne uniquement avec des fichiers texte",
      "ADD copie sans conserver les permissions",
      "Il n'y a aucune différence, ADD est l'ancien nom de COPY"),
     0, 2,
     "Les deux copient, mais ADD en fait davantage. La recommandation "
     "officielle est de préférer COPY, plus prévisible."),

    ("Que fait l'option -d de `docker run -d nginx` ?",
     ("Elle lance le conteneur en arrière-plan",
      "Elle supprime le conteneur à son arrêt",
      "Elle active le mode debug du démon",
      "Elle monte le répertoire courant dans le conteneur"),
     0, 1,
     "`-d` pour *detached* : le terminal est rendu tout de suite. "
     "C'est `--rm` qui supprime le conteneur à son arrêt."),

    ("Que signifie `docker run -p 8080:80 nginx` ?",
     ("Le port 8080 de la machine mène au port 80 du conteneur",
      "Le port 80 de la machine mène au port 8080 du conteneur",
      "Le conteneur écoute sur les deux ports à la fois",
      "Le conteneur ne peut utiliser que les ports 80 et 8080"),
     0, 2,
     "La publication se lit toujours hôte:conteneur. On visite donc "
     "http://localhost:8080 pour atteindre le nginx du conteneur."),

    ("À quoi sert un volume Docker ?",
     ("À conserver des données au-delà de la vie du conteneur",
      "À accélérer la construction des images",
      "À limiter la mémoire allouée au conteneur",
      "À partager le réseau entre plusieurs conteneurs"),
     0, 2,
     "Le système de fichiers d'un conteneur disparaît avec lui. Ce qui "
     "doit survivre — une base de données, des fichiers déposés — va "
     "dans un volume."),

    ("Que se passe-t-il quand on fait `docker stop` puis `docker start` "
     "sur un conteneur ?",
     ("Le conteneur repart avec son système de fichiers intact",
      "Le conteneur repart à l'état initial de l'image",
      "Le conteneur est recréé à partir du Dockerfile",
      "Les données du conteneur sont perdues"),
     0, 3,
     "Arrêter n'est pas supprimer. Les écritures faites dans le "
     "conteneur sont conservées tant qu'on ne fait pas `docker rm`."),

    ("Quelle commande construit une image à partir d'un Dockerfile ?",
     ("docker build -t monapp .",
      "docker create -t monapp .",
      "docker compile monapp",
      "docker image monapp ."),
     0, 1,
     "`-t` donne un nom à l'image, et le point désigne le contexte de "
     "construction — le répertoire envoyé au démon."),

    ("Pourquoi place-t-on `COPY requirements.txt` avant `COPY . .` "
     "dans un Dockerfile Python ?",
     ("Pour que le cache des couches évite de réinstaller à chaque build",
      "Parce que Docker refuse de copier un fichier après un répertoire",
      "Pour que pip trouve le fichier à la racine du conteneur",
      "Parce que l'ordre des COPY est imposé par la syntaxe"),
     0, 4,
     "Chaque instruction crée une couche mise en cache. Si le code "
     "change mais pas les dépendances, l'installation n'est pas rejouée."),

    ("Que fait `docker exec -it mon_conteneur bash` ?",
     ("Elle ouvre un shell interactif dans un conteneur qui tourne déjà",
      "Elle lance un nouveau conteneur à partir de l'image bash",
      "Elle exécute le script bash du Dockerfile",
      "Elle redémarre le conteneur en mode interactif"),
     0, 2,
     "`exec` entre dans un conteneur vivant ; `run` en crée un nouveau. "
     "`-it` demande un terminal interactif."),

    ("À quoi sert un fichier .dockerignore ?",
     ("À exclure des fichiers du contexte envoyé au démon",
      "À empêcher Docker de lire certaines variables d'environnement",
      "À masquer des conteneurs dans `docker ps`",
      "À interdire la publication de certains ports"),
     0, 3,
     "Sans lui, `docker build` envoie tout le répertoire — y compris "
     ".git et node_modules. Le build est plus lent, et l'image risque "
     "d'embarquer ce qu'elle ne devrait pas."),

    ("Quelle différence entre `docker-compose up` et `docker run` ?",
     ("Compose lance plusieurs services décrits dans un fichier YAML",
      "Compose ne sait lancer qu'un seul conteneur à la fois",
      "docker run gère les dépendances entre conteneurs, pas Compose",
      "Les deux commandes sont strictement équivalentes"),
     0, 3,
     "Compose décrit une application entière — services, réseaux, "
     "volumes — dans un fichier versionné, au lieu d'une ligne de "
     "commande à retenir."),

    ("Un conteneur s'arrête immédiatement après `docker run`. "
     "Quelle est la cause la plus probable ?",
     ("Son processus principal s'est terminé",
      "Le démon Docker manque de mémoire",
      "Le port publié est déjà occupé",
      "L'image a été téléchargée de façon incomplète"),
     0, 4,
     "Un conteneur vit le temps de son processus numéro 1. S'il rend la "
     "main, le conteneur s'arrête. `docker logs` dit pourquoi."),
)

def _tourner(choices, answer, rang):
    """Fait glisser les propositions pour que la bonne change de place.

    L'élève, lui, reçoit de toute façon un ordre tiré au sort par sa copie
    (cf. `shuffled_blanks`) : ce décalage ne sert qu'à la lecture côté
    enseignant et au modèle Excel.
    """
    decalage = rang % len(choices)
    tournees = tuple(choices[-decalage:] + choices[:-decalage]) if decalage \
        else tuple(choices)
    return tournees, (answer + decalage) % len(choices)


def _build(rang, question, choices, answer, level, explanation):
    choices, answer = _tourner(choices, answer, rang)
    return qcm_pattern("qcm_docker_%02d" % rang, rang, question,
                       choices, answer, level, explanation)


PATTERNS = tuple(
    _build(number + 1, *entree) for number, entree in enumerate(QUESTIONS)
)

MODULE = Module(
    key="qcm_docker",
    title="Docker : les bases",
    level=2,
    summary="Images et conteneurs, commandes du quotidien, Dockerfile, "
            "ports et volumes.",
    keys=tuple(p.key for p in PATTERNS),
)
