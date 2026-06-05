"""
Distribuição de Skellam para diferença de golos em futebol.
"""

import math
from scipy.stats import skellam
from scipy.optimize import minimize


def skellam_match_probs(lam1, lam2):
    """
    Calcula probabilidades de resultado usando a distribuição de Skellam.
    A diferença de golos (home - away) segue Skellam(lam1, lam2).

    Params:
        lam1: taxa de golos esperada da casa
        lam2: taxa de golos esperada de fora

    Returns:
        dict com:
            prob_home: P(home wins) = P(diff > 0)
            prob_draw: P(draw) = P(diff == 0)
            prob_away: P(away wins) = P(diff < 0)
            mean_diff: média da diferença (lam1 - lam2)
            std_diff: desvio padrão da diferença (sqrt(lam1 + lam2))
    """
    lam1 = max(0.01, float(lam1))
    lam2 = max(0.01, float(lam2))

    # P(diff == 0): empate
    prob_draw = float(skellam.pmf(0, lam1, lam2))

    # P(diff < 0): vitória de fora
    prob_away = float(skellam.cdf(-1, lam1, lam2))

    # P(diff > 0): vitória da casa = 1 - P(diff <= 0)
    prob_home = float(1.0 - skellam.cdf(0, lam1, lam2))

    # Garantir não-negatividade e normalizar
    prob_home = max(0.0, prob_home)
    prob_draw = max(0.0, prob_draw)
    prob_away = max(0.0, prob_away)
    total = prob_home + prob_draw + prob_away
    if total > 0:
        prob_home /= total
        prob_draw /= total
        prob_away /= total

    mean_diff = lam1 - lam2
    std_diff = math.sqrt(lam1 + lam2)

    return {
        "prob_home": prob_home,
        "prob_draw": prob_draw,
        "prob_away": prob_away,
        "mean_diff": mean_diff,
        "std_diff": std_diff,
    }


def implied_lambdas_from_odds(prob_home, prob_draw, prob_away, mean_goals=2.5):
    """
    Estima lambdas a partir de probabilidades de mercado usando o modelo de Skellam.

    Params:
        prob_home: probabilidade de vitória da casa
        prob_draw: probabilidade de empate
        prob_away: probabilidade de vitória de fora
        mean_goals: total de golos esperados (restrição)

    Returns:
        (lam1, lam2): taxas de golos estimadas
    """
    # Normalizar
    total = prob_home + prob_draw + prob_away
    if total <= 0:
        return (1.4, 1.1)
    prob_home = prob_home / total
    prob_draw = prob_draw / total
    prob_away = prob_away / total

    def objective(params):
        l1, l2 = params
        if l1 <= 0 or l2 <= 0:
            return 1e9
        try:
            preds = skellam_match_probs(l1, l2)
            err = (
                (preds["prob_home"] - prob_home) ** 2
                + (preds["prob_draw"] - prob_draw) ** 2
                + (preds["prob_away"] - prob_away) ** 2
            )
            # Penalidade suave: total de golos
            penalty = 0.05 * ((l1 + l2) - mean_goals) ** 2
            return err + penalty
        except Exception:
            return 1e9

    # Inicialização baseada nas probabilidades
    # Equipa favorita tem lambda mais alto
    l1_init = mean_goals * (0.4 + prob_home * 0.4)
    l2_init = mean_goals * (0.4 + prob_away * 0.4)
    l1_init = max(0.3, min(l1_init, 3.5))
    l2_init = max(0.3, min(l2_init, 3.5))

    result = minimize(
        objective,
        x0=[l1_init, l2_init],
        method="Nelder-Mead",
        options={"xatol": 1e-6, "fatol": 1e-6, "maxiter": 5000},
    )

    lam1, lam2 = result.x
    return (max(0.05, float(lam1)), max(0.05, float(lam2)))


def goal_diff_distribution(lam1, lam2, max_diff=8):
    """
    Distribuição completa da diferença de golos.

    Params:
        lam1: taxa de golos da casa
        lam2: taxa de golos de fora
        max_diff: diferença máxima a considerar (positiva e negativa)

    Returns:
        lista de dicts com:
            diff: diferença de golos (int, negativo = vitória de fora)
            prob: probabilidade desta diferença
            cumulative: probabilidade acumulada até este ponto
    """
    lam1 = max(0.01, float(lam1))
    lam2 = max(0.01, float(lam2))

    diffs = list(range(-max_diff, max_diff + 1))
    probs = [float(skellam.pmf(d, lam1, lam2)) for d in diffs]

    # Normalizar
    total = sum(probs)
    if total > 0:
        probs = [p / total for p in probs]

    result = []
    cumulative = 0.0
    for d, p in zip(diffs, probs):
        cumulative += p
        result.append({
            "diff": d,
            "prob": p,
            "cumulative": min(1.0, cumulative),
        })
    return result


def handicap_probability(lam1, lam2, handicap):
    """
    Probabilidade de a casa ganhar com handicap H.
    P(goals_home - goals_away + handicap > 0)
    = P(skellam > -handicap)
    = 1 - CDF(-handicap - 1) para handicap inteiro
    Para handicap fraccionário (ex. -0.5, +1.5), usa CDF contínuo aproximado.

    Params:
        lam1: taxa de golos da casa
        lam2: taxa de golos de fora
        handicap: handicap aplicado à casa (ex. -1.5, 0, +0.5)

    Returns:
        float: P(casa ganha com handicap)
    """
    lam1 = max(0.01, float(lam1))
    lam2 = max(0.01, float(lam2))

    # Precisamos P(diff + handicap > 0) = P(diff > -handicap)
    threshold = -handicap
    if threshold == int(threshold):
        # Valor inteiro: P(diff > threshold) = 1 - CDF(threshold)
        prob = float(1.0 - skellam.cdf(int(threshold), lam1, lam2))
    else:
        # Valor fraccionário: P(diff > threshold) = P(diff >= ceil(threshold))
        import math
        ceil_threshold = math.ceil(threshold)
        prob = float(1.0 - skellam.cdf(ceil_threshold - 1, lam1, lam2))

    return float(max(0.0, min(1.0, prob)))


def expected_goals_from_history(records):
    """
    Calcula médias de golos esperados a partir do histórico do football-dashboard.
    Usa os campos xg_home e xg_away como proxy de golos.

    Params:
        records: lista de dicts com campos do history.json

    Returns:
        dict com:
            avg_home: média de xg_home
            avg_away: média de xg_away
            avg_total: média de xg_home + xg_away
            by_league: dict mapeando liga -> dict com avg_home, avg_away, avg_total, n
    """
    if not records:
        return {
            "avg_home": 0.0,
            "avg_away": 0.0,
            "avg_total": 0.0,
            "by_league": {},
        }

    home_goals = []
    away_goals = []
    by_league = {}

    for rec in records:
        try:
            xg_h = float(rec.get("xg_home", 0) or 0)
            xg_a = float(rec.get("xg_away", 0) or 0)
        except (ValueError, TypeError):
            continue

        # Ignorar registos sem dados de xG
        if xg_h == 0 and xg_a == 0:
            continue

        home_goals.append(xg_h)
        away_goals.append(xg_a)

        league = rec.get("league", "Unknown")
        if league not in by_league:
            by_league[league] = {"home_goals": [], "away_goals": []}
        by_league[league]["home_goals"].append(xg_h)
        by_league[league]["away_goals"].append(xg_a)

    if not home_goals:
        return {
            "avg_home": 0.0,
            "avg_away": 0.0,
            "avg_total": 0.0,
            "by_league": {},
        }

    avg_home = sum(home_goals) / len(home_goals)
    avg_away = sum(away_goals) / len(away_goals)
    avg_total = sum(h + a for h, a in zip(home_goals, away_goals)) / len(home_goals)

    league_stats = {}
    for league, data in by_league.items():
        hg = data["home_goals"]
        ag = data["away_goals"]
        n = len(hg)
        lh = sum(hg) / n
        la = sum(ag) / n
        league_stats[league] = {
            "avg_home": lh,
            "avg_away": la,
            "avg_total": lh + la,
            "n": n,
        }

    return {
        "avg_home": avg_home,
        "avg_away": avg_away,
        "avg_total": avg_total,
        "by_league": league_stats,
    }
