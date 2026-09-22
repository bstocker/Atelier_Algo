"""Bareme de la session : note sur 20, moins les penalites.

Deux penalites se cumulent, et elles ne repondent pas a la meme crainte.

Les **sorties de fenetre** retirent des points a la copie entiere : elles
sanctionnent le fait d'aller chercher la reponse ailleurs.

Les **essais manques** retirent des points au seul exercice en cours, au
prorata de sa valeur. Sans eux, un eleve pourrait essayer les reponses une
par une jusqu'a tomber juste et decrocher la note pleine ; avec eux, les
avoir toutes essayees ramene l'exercice a zero.

Cette seconde sanction ne s'applique **pas en mode examen** : elle suppose
que l'application dise a l'eleve quand il tombe juste, ce qu'elle ne fait
plus. La copie y est jugee sur la reponse qu'elle porte a la remise —
`shares_of(..., count_wrong=False)`.

Ce module ne connait pas le catalogue : le nombre de reponses possibles
d'un exercice lui est passe en argument.
"""

MAX_SCORE = 20.0

# Penalite appliquee selon le rang de la sortie de fenetre.
# 1re sortie : avertissement seul. Au-dela de la 3e, on reste a -3.
PENALTY_BY_ORDINAL = {1: 0.0, 2: 2.0, 3: 3.0}
PENALTY_BEYOND = 3.0

# Delai laisse a l'etudiant pour revenir, affiche en decompte.
RETURN_DELAY_SECONDS = 3


def penalty_for(ordinal):
    """Points retires a la n-ieme sortie de fenetre."""
    return PENALTY_BY_ORDINAL.get(ordinal, PENALTY_BEYOND)


# --------------------------------------------------------------------------
# Valeur d'un exercice et cout des essais manques
# --------------------------------------------------------------------------

def exercise_value(total):
    """Points que vaut un exercice dans une session qui en compte `total`."""
    if total <= 0:
        return 0.0
    return MAX_SCORE / total


def allowance(choices):
    """Nombre d'essais manques qui ramenent un exercice a zero.

    Un exercice a `choices` reponses possibles, donc `choices - 1` fausses :
    c'est le nombre d'essais qu'il faut pour les avoir toutes tentees.
    """
    return max(1, int(choices) - 1)


def kept_share(choices, wrong_attempts):
    """Part de la valeur d'un exercice qui subsiste apres des essais manques.

    La decroissance est lineaire et s'arrete a zero : un essai manque coute
    toujours la meme fraction, et les avoir tous faits ne rapporte plus rien.
    Un exercice a quatre reponses perd donc un tiers de sa valeur par essai
    manque ; un exercice a seize reponses, un quinzieme.
    """
    return max(0.0, 1.0 - float(wrong_attempts) / allowance(choices))


def attempt_cost(total, choices):
    """Points qu'un essai manque retire a un exercice."""
    return exercise_value(total) / allowance(choices)


def shares_of(tasks, choices_of, count_wrong=True):
    """Parts gardees sur les exercices reussis, dans l'ordre des taches.

    `choices_of` rend le nombre de reponses possibles d'un exercice : le
    bareme reste ainsi ignorant du catalogue. Les exercices non reussis
    ne rapportent rien et n'apparaissent pas ici.

    `count_wrong` a False, un exercice reussi garde sa valeur pleine quels
    qu'aient ete les essais : c'est le regime du **mode examen**. La
    sanction y perdrait sa cible — elle existe pour qu'un eleve ne puisse
    pas essayer les reponses une par une jusqu'a tomber juste, et cela
    suppose qu'on lui dise quand il tombe juste. En examen on ne le lui dit
    pas, et la copie est jugee sur la reponse qu'elle porte a la remise.
    """
    return [kept_share(choices_of(task["pattern_key"]),
                       task["wrong_attempts"] if count_wrong else 0)
            for task in tasks if task["solved"]]


# --------------------------------------------------------------------------
# Note
# --------------------------------------------------------------------------

def base_score(shares, total):
    """Note brute sur 20 : somme des parts gardees, rapportee au total.

    Un exercice reussi du premier coup rapporte une part entiere ; un
    exercice arrache apres des essais manques, une part entamee.
    """
    if total <= 0:
        return 0.0
    return round(MAX_SCORE * sum(shares) / total, 2)


def final_score(shares, total, penalty_points):
    """Note finale, bornee a l'intervalle [0, 20]."""
    score = base_score(shares, total) - float(penalty_points)
    return round(min(MAX_SCORE, max(0.0, score)), 2)
