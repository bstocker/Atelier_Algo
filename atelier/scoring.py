"""Bareme de la session : note sur 20, moins les penalites de sortie."""

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


def base_score(solved, total):
    """Note brute sur 20, proportionnelle aux motifs reussis."""
    if total <= 0:
        return 0.0
    return round(MAX_SCORE * solved / total, 2)


def final_score(solved, total, penalty_points):
    """Note finale, bornee a l'intervalle [0, 20]."""
    score = base_score(solved, total) - float(penalty_points)
    return round(min(MAX_SCORE, max(0.0, score)), 2)
