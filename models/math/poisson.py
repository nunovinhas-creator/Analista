"""
Bivariate Dixon-Coles Poisson model para previsão de resultados de futebol.
"""

import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize


def dixon_coles_tau(goals_h, goals_a, lam, mu, rho):
    """
    Factores de correcção de Dixon-Coles para baixos scores (0-0, 1-0, 0-1, 1-1).
    Retorna 1.0 para todos os outros scores.
    """
    if goals_h == 0 and goals_a == 0:
        return 1.0 - lam * mu * rho
    elif goals_h == 1 and goals_a == 0:
        return 1.0 + mu * rho
    elif goals_h == 0 and goals_a == 1:
        return 1.0 + lam * rho
    elif goals_h == 1 and goals_a == 1:
        return 1.0 - rho
    else:
        return 1.0


def bivariate_poisson_pmf(goals_h, goals_a, lam, mu, rho=0.0):
    """
    PMF da distribuição de Poisson bivariada com correcção Dixon-Coles.

    Params:
        goals_h: golos da equipa da casa
        goals_a: golos da equipa de fora
        lam: taxa esperada de golos da casa
        mu: taxa esperada de golos de fora
        rho: parâmetro de correlação Dixon-Coles (tipicamente negativo, ex. -0.1)

    Returns:
        probabilidade do score (goals_h, goals_a)
    """
    if lam <= 0 or mu <= 0:
        return 0.0

    p_h = poisson.pmf(goals_h, lam)
    p_a = poisson.pmf(goals_a, mu)
    tau = dixon_coles_tau(goals_h, goals_a, lam, mu, rho)

    prob = tau * p_h * p_a
    # Garantir que a probabilidade é não-negativa
    return max(0.0, prob)


def score_matrix(lam, mu, rho=0.0, max_goals=10):
    """
    Matriz de probabilidades de score [goals_h x goals_a].

    Returns:
        np.ndarray de forma (max_goals+1, max_goals+1)
        onde mat[i, j] = P(home=i, away=j)
    """
    mat = np.zeros((max_goals + 1, max_goals + 1))
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            mat[i, j] = bivariate_poisson_pmf(i, j, lam, mu, rho)

    # Normalizar para garantir que soma a 1 (pequena correcção numérica)
    total = mat.sum()
    if total > 0:
        mat = mat / total
    return mat


def predict_market_probs(lam, mu, rho=0.0, max_goals=10):
    """
    Calcula probabilidades de mercado a partir dos lambdas Poisson.

    Returns:
        dict com:
            prob_home: P(home wins)
            prob_draw: P(draw)
            prob_away: P(away wins)
            prob_over25: P(total goals > 2.5)
            prob_btts: P(ambas equipas marcam)
            lambda_home: lam (para referência)
            lambda_away: mu (para referência)
    """
    mat = score_matrix(lam, mu, rho, max_goals)

    prob_home = float(np.sum(np.tril(mat, -1)))   # goals_h > goals_a
    prob_away = float(np.sum(np.triu(mat, 1)))    # goals_a > goals_h
    prob_draw = float(np.sum(np.diag(mat)))

    # Over 2.5: total de golos >= 3
    prob_over25 = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            if i + j > 2:
                prob_over25 += mat[i, j]

    # BTTS: ambas equipas marcam pelo menos 1 golo
    prob_btts = 0.0
    for i in range(1, max_goals + 1):
        for j in range(1, max_goals + 1):
            prob_btts += mat[i, j]

    # Normalizar para garantir consistência
    total_1x2 = prob_home + prob_draw + prob_away
    if total_1x2 > 0:
        prob_home /= total_1x2
        prob_draw /= total_1x2
        prob_away /= total_1x2

    return {
        "prob_home": float(np.clip(prob_home, 0.0, 1.0)),
        "prob_draw": float(np.clip(prob_draw, 0.0, 1.0)),
        "prob_away": float(np.clip(prob_away, 0.0, 1.0)),
        "prob_over25": float(np.clip(prob_over25, 0.0, 1.0)),
        "prob_btts": float(np.clip(prob_btts, 0.0, 1.0)),
        "lambda_home": float(lam),
        "lambda_away": float(mu),
    }


def estimate_lambdas(prob_home, prob_draw, prob_away, expected_goals=2.5):
    """
    Estima lambdas de ataque a partir de probabilidades de mercado.
    Usa scipy.optimize para minimizar a distância entre probabilidades previstas
    e probabilidades observadas.

    Params:
        prob_home: probabilidade de vitória da casa (0-1)
        prob_draw: probabilidade de empate (0-1)
        prob_away: probabilidade de vitória de fora (0-1)
        expected_goals: total de golos esperados (restrição suave)

    Returns:
        (lam_home, lam_away): tupla com as taxas estimadas
    """
    # Normalizar probabilidades de entrada
    total = prob_home + prob_draw + prob_away
    if total <= 0:
        return (1.3, 1.2)
    prob_home = prob_home / total
    prob_draw = prob_draw / total
    prob_away = prob_away / total

    def objective(params):
        lam_h, lam_a = params
        if lam_h <= 0 or lam_a <= 0:
            return 1e9
        try:
            preds = predict_market_probs(lam_h, lam_a, rho=0.0, max_goals=8)
            # Erro quadrático nas probabilidades 1X2
            err_h = (preds["prob_home"] - prob_home) ** 2
            err_d = (preds["prob_draw"] - prob_draw) ** 2
            err_a = (preds["prob_away"] - prob_away) ** 2
            # Penalidade suave para total de golos esperados
            total_goals = lam_h + lam_a
            penalty = 0.1 * (total_goals - expected_goals) ** 2
            return err_h + err_d + err_a + penalty
        except Exception:
            return 1e9

    # Estimativa inicial simples
    # Mais golos em casa para equipas favoritas
    lam_home_init = expected_goals * prob_home + expected_goals * 0.3
    lam_away_init = expected_goals * prob_away + expected_goals * 0.3
    lam_home_init = max(0.3, min(lam_home_init, 4.0))
    lam_away_init = max(0.3, min(lam_away_init, 4.0))

    result = minimize(
        objective,
        x0=[lam_home_init, lam_away_init],
        method="Nelder-Mead",
        options={"xatol": 1e-5, "fatol": 1e-5, "maxiter": 5000},
        bounds=None,
    )

    lam_h, lam_a = result.x
    lam_h = max(0.1, float(lam_h))
    lam_a = max(0.1, float(lam_a))

    return (lam_h, lam_a)


def simulate_poisson_probs(lam_home, lam_away, rho=-0.1):
    """
    Interface simples: dado lambdas, retorna todas as probabilidades de mercado.

    Params:
        lam_home: taxa de golos esperada da casa
        lam_away: taxa de golos esperada de fora
        rho: correlação Dixon-Coles (default -0.1)

    Returns:
        dict com prob_home, prob_draw, prob_away, prob_over25, prob_btts,
              lambda_home, lambda_away
    """
    lam_home = max(0.1, float(lam_home))
    lam_away = max(0.1, float(lam_away))
    return predict_market_probs(lam_home, lam_away, rho=rho, max_goals=10)
