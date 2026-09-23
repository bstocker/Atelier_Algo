"""Module « Masques réseau » : préfixe, masque, réseau, diffusion, hôtes.

Le masque est la seule clé de l'adressage IP : il dit quelle part d'une
adresse désigne le réseau, et quelle part désigne la machine. Tout le
reste — adresse du réseau, diffusion, nombre de machines, découpage —
s'en déduit par un ET, un OU, ou une puissance de deux.
"""

from ..engine import Module, Pattern, _opts, debug_pattern, predict_from
from .reseau_commun import diffusion, entier, hotes, lecon, pointee, reseau

# Adresses de poste. Aucun octet de la partie hôte n'est nul ni ne vaut
# 255, sans quoi deux masques voisins pourraient donner le même réseau.
POSTES = ("192.168.1.37", "192.168.10.200", "10.0.5.12", "172.16.40.99",
          "192.168.100.7", "10.20.30.40")

# Masques des exercices à octets entiers : /8, /16, /24.
MASQUES_ENTIERS = ("255.0.0.0", "255.255.0.0", "255.255.255.0")

# Adresses du poste A, dans 192.168.<c>.<d>. Les cinq bits de poids faible
# de d ne sont ni tous à 0 ni tous à 1 : ni A ni ses voisins ne tombent
# sur l'adresse d'un réseau ou d'une diffusion, en /26 comme en /27.
VOISINAGES = ((5, 37), (12, 70), (1, 140), (30, 200), (8, 100), (20, 13))

# Adresses que le masque /20 coupe au milieu du troisième octet.
COUPEES = ("172.16.45.10", "10.1.200.33", "192.168.77.5", "172.20.130.250",
           "10.8.19.1", "192.168.250.100")

# Troisième octet des réseaux en /24 qu'on découpe.
SALLES = (7, 42, 128, 200)

# Rappel des prédictions : le rappel par défaut parle de boucles.
PREDIRE = (
    "Ne devinez pas : **posez le calcul**, en binaire pour l'octet que le "
    "masque coupe.",
    "Les espaces comptent. Une ligne décalée d'un espace est fausse.",
    "Les espaces en fin de ligne, eux, sont ignorés.",
)


def _poste(p):
    return {"ip": POSTES[p["g"]]}


# --------------------------------------------------------------------------
# L'adresse du réseau
# --------------------------------------------------------------------------

RESEAU = Pattern(
    key="net_reseau",
    name="L'adresse du réseau",
    brief="Trouver l'adresse du réseau d'une machine placée dans un réseau "
          "en /24.",
    why="Le masque garde la partie réseau de l'adresse, et efface le reste.",
    lesson=lecon(
        "Une adresse IPv4 s'écrit en quatre **octets** : quatre nombres de "
        "0 à 255, soit 32 bits en tout.",
        "`/24` est la notation **CIDR** : les 24 premiers bits du masque "
        "sont à 1, les 8 suivants à 0. En décimal, cela donne "
        "`255.255.255.0`.",
        "L'adresse du réseau est `Adresse ET Masque`, octet par octet : un "
        "octet ET 255 reste lui-même, un octet ET 0 devient 0.",
    ),
    dims=(("g", 0, 5),),
    derive=_poste,
    tpl="""Adresse : @ip@/24
Masque  : @masque@
Réseau  = Adresse ET Masque""",
    blanks={
        "masque": ("Masque à appliquer", _opts(
            ("a", "255.255.255.0", lambda p: "255.255.255.0"),
            ("b", "255.255.0.0", lambda p: "255.255.0.0"),
            ("c", "255.0.0.0", lambda p: "255.0.0.0"),
            ("d", "255.255.255.255", lambda p: "255.255.255.255"),
        )),
    },
    ref={"masque": "a"},
    rows=lambda p, get: ["Réseau : %s" % reseau(p["ip"], get("masque")(p))],
    level=1,
)


# --------------------------------------------------------------------------
# Combien de machines ?
# --------------------------------------------------------------------------

HOTES = Pattern(
    key="net_hotes",
    name="Combien de machines ?",
    brief="Compter les adresses qu'on peut donner à des machines dans un "
          "réseau de préfixe p.",
    why="Chaque bit d'hôte double le nombre d'adresses ; deux sont réservées.",
    lesson=lecon(
        "Le préfixe `p` compte les bits du **réseau**. Il reste `32 - p` "
        "bits pour numéroter les machines : les bits d'**hôte**.",
        "Avec `k` bits, on écrit `2^k` nombres différents : 8 bits donnent "
        "256 adresses.",
        "Deux adresses ne vont jamais à une machine : celle du **réseau** "
        "(bits d'hôte tous à 0) et celle de **diffusion** (tous à 1).",
    ),
    dims=(("p", 24, 29),),
    tpl="""Réseau      : 192.168.1.0/@p@
Préfixe p   : @p@
Bits d'hôte = 32 - p
Hôtes       = @formule@""",
    blanks={
        "formule": ("Nombre d'adresses utilisables", _opts(
            ("a", "2^(32 - p) - 2", lambda p: hotes(p["p"])),
            ("b", "2^(32 - p)", lambda p: 2 ** (32 - p["p"])),
            ("c", "2^p - 2", lambda p: 2 ** p["p"] - 2),
            ("d", "32 - p", lambda p: 32 - p["p"]),
        )),
    },
    ref={"formule": "a"},
    rows=lambda p, get: ["Hôtes : %d" % get("formule")(p)],
    level=2,
)


# --------------------------------------------------------------------------
# L'adresse de diffusion
# --------------------------------------------------------------------------

def _poste_masque(p):
    return {"ip": POSTES[p["g"]], "masque": MASQUES_ENTIERS[p["m"]]}


DIFFUSION = Pattern(
    key="net_diffusion",
    name="L'adresse de diffusion",
    brief="Trouver l'adresse qui atteint toutes les machines du réseau à la "
          "fois.",
    why="La diffusion est la dernière adresse du réseau : bits d'hôte à 1.",
    lesson=lecon(
        "`NON Masque` inverse chaque bit : `255.255.255.0` devient "
        "`0.0.0.255`. Il désigne la partie **hôte**.",
        "`Adresse OU x` met à 1 les bits où `x` vaut 1, et garde les "
        "autres.",
        "La **diffusion** (*broadcast*) garde la partie réseau et met la "
        "partie hôte à 1 : c'est la dernière adresse du réseau.",
        "À l'inverse, `Adresse ET Masque` met la partie hôte à 0 : c'est "
        "la première, l'adresse du réseau.",
    ),
    dims=(("g", 0, 5), ("m", 0, 2)),
    derive=_poste_masque,
    tpl="""Adresse   : @ip@
Masque    : @masque@
Diffusion = @operation@""",
    blanks={
        "operation": ("Opération à effectuer", _opts(
            ("a", "Adresse OU (NON Masque)",
             lambda p: diffusion(p["ip"], p["masque"])),
            ("b", "Adresse ET Masque",
             lambda p: reseau(p["ip"], p["masque"])),
            ("c", "Adresse OU Masque",
             lambda p: pointee(entier(p["ip"]) | entier(p["masque"]))),
            ("d", "Adresse ET (NON Masque)",
             lambda p: pointee(entier(p["ip"])
                               & ~entier(p["masque"]) & 0xFFFFFFFF)),
        )),
    },
    ref={"operation": "a"},
    rows=lambda p, get: ["Diffusion : %s" % get("operation")(p)],
    level=2,
)


# --------------------------------------------------------------------------
# Sur le même réseau ?
# --------------------------------------------------------------------------

def _voisinage(p):
    """Le poste A, et quatre voisins choisis pour départager les masques.

    Chaque voisin diffère de A par un seul bit du dernier octet — ou par
    le troisième octet, pour le dernier. Le bit changé décide à partir de
    quel préfixe il quitte le réseau de A : chaque mauvais masque se
    trompe donc sur au moins un voisin.
    """
    c, d = VOISINAGES[p["g"]]
    voisins = sorted([d ^ 0x20, d ^ 0x40, d ^ 0x80])
    adresses = ["192.168.%d.%d" % (c, x) for x in voisins]
    adresses.append("192.168.%d.%d" % (c + 1, d))
    return {"a": "192.168.%d.%d" % (c, d), "voisins": adresses,
            "liste": "\n".join("Voisin  : %s" % v for v in adresses)}


def _meme_reseau(p, get):
    m = get("masque")(p)
    return ["%s : %s" % (v, "même réseau" if reseau(v, m) == reseau(p["a"], m)
                         else "autre réseau")
            for v in p["voisins"]]


MEME_RESEAU = Pattern(
    key="net_meme_reseau",
    name="Sur le même réseau ?",
    brief="Le poste A est dans un réseau en /26. Dire lesquels de ses "
          "voisins il peut joindre directement, sans passer par un routeur.",
    why="Deux machines sont voisines quand le masque leur donne le même "
        "réseau.",
    lesson=lecon(
        "Deux machines sont sur le **même réseau** quand `Adresse ET "
        "Masque` donne le même résultat pour les deux. Sinon, il faut un "
        "**routeur** entre elles.",
        "Un masque qui ne finit pas sur un octet entier coupe un octet en "
        "deux : `/26` garde 2 bits du dernier octet, soit `11000000` = 192.",
        "Les valeurs possibles d'un octet de masque sont peu nombreuses : "
        "128, 192, 224, 240, 248, 252, 254, 255. Chacune ajoute un bit à 1.",
    ),
    dims=(("g", 0, 5),),
    derive=_voisinage,
    tpl="""Poste A : @a@/26
Masque  : @masque@
@liste@
Même réseau = (A ET Masque) == (Voisin ET Masque)""",
    blanks={
        "masque": ("Masque d'un /26", _opts(
            ("a", "255.255.255.192", lambda p: "255.255.255.192"),
            ("b", "255.255.255.0", lambda p: "255.255.255.0"),
            ("c", "255.255.255.128", lambda p: "255.255.255.128"),
            ("d", "255.255.255.224", lambda p: "255.255.255.224"),
        )),
    },
    ref={"masque": "a"},
    rows=_meme_reseau,
    level=3,
)


# --------------------------------------------------------------------------
# Découper un réseau en quatre
# --------------------------------------------------------------------------

def _plages(p, get):
    """Les sous-réseaux du /24 au préfixe choisi, de la première adresse
    (le réseau) à la dernière (la diffusion)."""
    taille = 2 ** (32 - get("prefixe")(p))
    base = entier("192.168.%d.0" % p["c"])
    return ["%s à %s" % (pointee(debut), pointee(debut + taille - 1))
            for debut in range(base, base + 256, taille)]


DECOUPAGE = Pattern(
    key="net_decoupage",
    name="Découper un réseau en quatre",
    brief="Découper le réseau en quatre sous-réseaux de même taille, et "
          "donner la plage de chacun.",
    why="Emprunter k bits à la partie hôte crée 2^k sous-réseaux.",
    lesson=lecon(
        "Allonger le préfixe **emprunte** des bits à la partie hôte : "
        "chaque bit emprunté double le nombre de sous-réseaux, et divise "
        "leur taille par deux.",
        "Un bit donne 2 sous-réseaux, deux bits 4, trois bits 8.",
        "Un /24 compte 256 adresses. Coupé en 4, chaque morceau en garde "
        "64 : de `.0` à `.63`, de `.64` à `.127`, etc.",
    ),
    dims=(("g", 0, 3),),
    derive=lambda p: {"c": SALLES[p["g"]]},
    tpl="""Réseau          : 192.168.@c@.0/24
Découpage       : 4 sous-réseaux de même taille
Nouveau préfixe : @prefixe@
Plages          = du réseau à la diffusion de chaque sous-réseau""",
    blanks={
        "prefixe": ("Préfixe des sous-réseaux", _opts(
            ("a", "/26", lambda p: 26),
            ("b", "/25", lambda p: 25),
            ("c", "/27", lambda p: 27),
            ("d", "/28", lambda p: 28),
        )),
    },
    ref={"prefixe": "a"},
    rows=_plages,
    level=3,
)


# --------------------------------------------------------------------------
# Un masque qui coupe un octet
# --------------------------------------------------------------------------

def _reseau_et_diffusion(p, get):
    m = get("masque")(p)
    return ["Réseau : %s" % reseau(p["ip"], m),
            "Diffusion : %s" % diffusion(p["ip"], m)]


MASQUE_COUPE = Pattern(
    key="net_masque_coupe",
    name="Un masque qui coupe un octet",
    brief="Trouver le réseau et la diffusion d'une machine placée dans un "
          "réseau en /20.",
    why="Seul l'octet coupé demande un calcul en binaire ; les autres "
        "valent 255 ou 0.",
    lesson=lecon(
        "`/20`, c'est 16 bits pour les deux premiers octets, et **4** de "
        "plus dans le troisième : `11110000` = 240.",
        "Les octets du masque à 255 recopient l'adresse, ceux à 0 "
        "l'effacent. Seul l'octet coupé se calcule, bit à bit.",
        "Dans l'octet coupé, le réseau avance par pas de `256 - 240 = 16` : "
        "0, 16, 32, 48… L'adresse du réseau est le multiple de 16 juste en "
        "dessous, la diffusion le suivant moins un.",
    ),
    dims=(("g", 0, 5),),
    derive=lambda p: {"ip": COUPEES[p["g"]]},
    tpl="""Adresse   : @ip@/20
Masque    : @masque@
Réseau    = Adresse ET Masque
Diffusion = Adresse OU (NON Masque)""",
    blanks={
        "masque": ("Masque d'un /20", _opts(
            ("a", "255.255.240.0", lambda p: "255.255.240.0"),
            ("b", "255.255.248.0", lambda p: "255.255.248.0"),
            ("c", "255.255.224.0", lambda p: "255.255.224.0"),
            ("d", "255.255.255.240", lambda p: "255.255.255.240"),
        )),
    },
    ref={"masque": "a"},
    rows=_reseau_et_diffusion,
    level=4,
)


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

def _salle(p):
    c, d = VOISINAGES[p["g"]]
    # Le poste reste dans la moitié basse du /24 : c'est là que le /25
    # l'enferme, loin de la passerelle en .254.
    return {"c": c, "d": d % 126 + 1, "num": p["g"] + 10}


BUG_PASSERELLE = debug_pattern(
    key="net_bug_passerelle",
    name="Bug : joindre la passerelle",
    sujet="Cette configuration",
    but="permettre au poste de joindre sa passerelle, pour sortir du réseau "
        "de la salle",
    defaut="masque 255.255.255.128 (/25) au lieu de 255.255.255.0 (/24) : "
           "la passerelle tombe dans l'autre moitié",
    dims=(("g", 0, 5),),
    derive=_salle,
    tpl="""# Poste PC-@num@
Adresse    : 192.168.@c@.@d@
Masque     : 255.255.255.128
Passerelle : 192.168.@c@.254
Réseau     = Adresse ET Masque
Diffusion  = Adresse OU (NON Masque)
Passerelle joignable = Passerelle entre Réseau et Diffusion""",
    attendu=lambda p: ["Réseau : 192.168.%d.0" % p["c"],
                       "Diffusion : 192.168.%d.255" % p["c"],
                       "Passerelle : joignable"],
    obtenu=lambda p: ["Réseau : %s" % reseau("192.168.%d.%d" % (p["c"], p["d"]),
                                              "255.255.255.128"),
                      "Diffusion : %s" % diffusion(
                          "192.168.%d.%d" % (p["c"], p["d"]),
                          "255.255.255.128"),
                      "Passerelle : hors du réseau"],
    diagnostics=(
        ("a", "Le masque `255.255.255.128` est un **/25** : il coupe le "
              "réseau en deux moitiés, et la passerelle en `.254` tombe "
              "dans celle où le poste n'est pas.",
         "Exact. 128 s'écrit `10000000` : un bit de plus pour le réseau, "
         "qui s'arrête alors en `.127`. Avec `255.255.255.0`, le réseau "
         "irait jusqu'en `.255` et engloberait la passerelle."),
        ("b", "Une passerelle doit toujours porter l'adresse en `.1` du "
              "réseau.",
         "Non : `.1` et `.254` sont deux conventions répandues, pas des "
         "règles. N'importe quelle adresse d'hôte du réseau convient."),
        ("c", "L'adresse du poste est celle du réseau : aucune machine ne "
              "peut la porter.",
         "Non : l'adresse du réseau finit par `.0`, et le poste n'y est "
         "pas. Les deux sorties affichent d'ailleurs le même réseau."),
        ("d", "Une passerelle doit être sur un **autre** réseau que le "
              "poste, puisqu'elle sert à en sortir.",
         "C'est l'inverse : le poste ne parle directement qu'à son propre "
         "réseau. Une passerelle hors de ce réseau est injoignable, et "
         "c'est justement ce que la sortie constate."),
    ),
    bonne="a",
    level=3,
)


def _plan(p):
    c = SALLES[p["g"]]
    base = 32 * (p["g"] + 1)
    return {"c": c, "base": base, "s1": base + 1, "s2": base + 2,
            "s3": base + 3, "r": base + 31}


BUG_PLAN = debug_pattern(
    key="net_bug_plan",
    name="Bug : le plan de la salle serveurs",
    sujet="Ce plan d'adressage",
    but="donner une adresse valable à chaque machine de la salle serveurs",
    defaut="le routeur reçoit la dernière adresse du /27, qui est celle de "
           "diffusion",
    dims=(("g", 0, 3),),
    derive=_plan,
    tpl="""# Salle serveurs
Réseau    : 192.168.@c@.@base@/27
Masque    : 255.255.255.224
Serveur 1 : 192.168.@c@.@s1@
Serveur 2 : 192.168.@c@.@s2@
Serveur 3 : 192.168.@c@.@s3@
Routeur   : 192.168.@c@.@r@""",
    attendu=lambda _p: ["Serveur 1 : adresse valable",
                        "Serveur 2 : adresse valable",
                        "Serveur 3 : adresse valable",
                        "Routeur : adresse valable"],
    obtenu=lambda _p: ["Serveur 1 : adresse valable",
                       "Serveur 2 : adresse valable",
                       "Serveur 3 : adresse valable",
                       "Routeur : adresse de diffusion, refusée"],
    diagnostics=(
        ("a", "Un /27 compte 32 adresses, du réseau à la base jusqu'à "
              "base + 31. La dernière est celle de **diffusion** : aucune "
              "machine ne peut la porter.",
         "Exact. `224` s'écrit `11100000` : il reste 5 bits d'hôte, donc "
         "32 adresses, dont la première (le réseau) et la dernière (la "
         "diffusion) sont réservées. Le routeur devait prendre base + 30."),
        ("b", "L'adresse du routeur est celle du **réseau**.",
         "Non : l'adresse du réseau est la **première** du bloc, celle "
         "qu'affiche la ligne `Réseau`. Le routeur a pris la dernière."),
        ("c", "Un /27 ne contient que 16 adresses : le routeur est hors du "
              "réseau.",
         "Non : 16 adresses, c'est un /28. Un /27 laisse 32 - 27 = 5 bits "
         "d'hôte, soit 32 adresses. Le routeur est bien dans le bloc."),
        ("d", "Le masque `255.255.255.224` ne correspond pas à un /27, mais "
              "à un /28.",
         "Non : `224` s'écrit `11100000`, trois bits à 1. Avec les 24 bits "
         "des trois premiers octets, cela fait bien 27."),
    ),
    bonne="a",
    level=4,
)


# --------------------------------------------------------------------------
# Prédiction
# --------------------------------------------------------------------------

PREDIRE_HOTES = predict_from(
    HOTES,
    key="net_predire_hotes",
    name="Prédire : le nombre de machines",
    why="Une puissance de deux, moins les deux adresses réservées.",
    level=2,
    output_format=("Hôtes : XXXX",),
    lesson=PREDIRE,
)

PREDIRE_MASQUE = predict_from(
    MASQUE_COUPE,
    key="net_predire_masque",
    name="Prédire : réseau et diffusion d'un /20",
    why="L'octet coupé se calcule en binaire, les autres se recopient.",
    level=4,
    output_format=(
        "Réseau : X.X.X.X",
        "Diffusion : X.X.X.X",
    ),
    lesson=PREDIRE,
)


PATTERNS = (RESEAU, HOTES, DIFFUSION, MEME_RESEAU, DECOUPAGE, MASQUE_COUPE,
            BUG_PASSERELLE, BUG_PLAN, PREDIRE_HOTES, PREDIRE_MASQUE)

MODULE = Module(
    key="reseau_masques",
    title="Masques réseau",
    level=2,
    summary="Passer du préfixe au masque, en tirer l'adresse du réseau, la "
            "diffusion et le nombre de machines, puis découper un réseau.",
    keys=tuple(p.key for p in PATTERNS),
)
