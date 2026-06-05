"""
Critério de Kelly e métricas de gestão de banca para apostas desportivas.
"""

import math
from scipy.optimize import minimize


def kelly_full(win_prob, odds):
    """
    Cálculo do Kelly completo (fracção óptima de banca a apostar).

    Params:
        win_prob: probabilidade de vitória (0-1)
        odds: odds decimais (ex. 2.0)

    Returns:
        float: fracção de banca (0-1); 0 se sem edge
    """
    if odds <= 1.0 or win_prob <= 0.0 or win_prob >= 1.0:
        return 0.0
    b = odds - 1.0  # lucro por unidade apostada
    q = 1.0 - win_prob
    kelly = (b * win_prob - q) / b
    return max(0.0, float(kelly))


def kelly_fraction(win_prob, odds, fraction=0.25):
    """
    Kelly fraccionário — reduz exposição ao risco dividindo pelo factor dado.

    Params:
        win_prob: probabilidade de vitória (0-1)
        odds: odds decimais
        fraction: fracção do Kelly a usar (default 0.25 = 1/4 Kelly)

    Returns:
        float: fracção de banca recomendada
    """
    full = kelly_full(win_prob, odds)
    return float(full * fraction)


def kelly_with_vig(win_prob, odds, vig=0.05):
    """
    Kelly ajustado para margem do bookmaker (vig/overround).
    Desconta a probabilidade de vitória pelo efeito da margem.

    Params:
        win_prob: probabilidade de vitória estimada (0-1)
        odds: odds decimais (com margem incluída)
        vig: margem do bookmaker (default 5%)

    Returns:
        float: fracção de banca ajustada
    """
    if odds <= 1.0 or win_prob <= 0.0:
        return 0.0
    # Odds fair ajustadas pela margem
    fair_odds = odds / (1.0 - vig)
    b = fair_odds - 1.0
    q = 1.0 - win_prob
    kelly = (b * win_prob - q) / b
    return max(0.0, float(kelly))


def portfolio_kelly(bets):
    """
    Kelly simultâneo para uma carteira de apostas independentes.
    Maximiza a taxa de crescimento logarítmica da banca.

    Params:
        bets: lista de tuplas (win_prob, odds) para cada aposta independente

    Returns:
        list of floats: stake óptima como % de banca para cada aposta
    """
    if not bets:
        return []

    n = len(bets)

    # Validar apostas
    valid = []
    for wp, odds in bets:
        wp = float(wp)
        odds = float(odds)
        if 0 < wp < 1 and odds > 1:
            valid.append((wp, odds))
        else:
            valid.append(None)

    # Verificar se há apostas válidas
    active_idx = [i for i, v in enumerate(valid) if v is not None]
    if not active_idx:
        return [0.0] * n

    def neg_log_growth(stakes):
        """Taxa de crescimento logarítmica negativa (a minimizar)."""
        growth = 0.0
        # 2^n cenários possíveis para apostas independentes
        active = [(stakes[i], valid[i][0], valid[i][1]) for i in active_idx]
        n_active = len(active)

        total = 0.0
        for scenario in range(2 ** n_active):
            prob_scenario = 1.0
            net_gain = 0.0
            for j in range(n_active):
                stake = active[j][0]
                wp = active[j][1]
                odds = active[j][2]
                win = bool(scenario & (1 << j))
                if win:
                    prob_scenario *= wp
                    net_gain += stake * (odds - 1.0)
                else:
                    prob_scenario *= (1.0 - wp)
                    net_gain -= stake

            bankroll_multiplier = 1.0 + net_gain
            if bankroll_multiplier <= 0:
                return 1e9
            growth += prob_scenario * math.log(bankroll_multiplier)
            total += prob_scenario

        return -growth

    # Inicializar com Kelly individual para cada aposta activa
    stakes_init = [0.0] * n
    for i in active_idx:
        wp, odds = valid[i]
        stakes_init[i] = kelly_full(wp, odds) * 0.25  # começar conservador

    # Optimizar
    bounds = [(0.0, 0.5)] * n  # max 50% por aposta
    try:
        result = minimize(
            neg_log_growth,
            x0=stakes_init,
            method="L-BFGS-B",
            bounds=bounds,
            options={"ftol": 1e-9, "maxiter": 1000},
        )
        stakes = [max(0.0, float(s)) for s in result.x]
    except Exception as e:
        print(f"[WARN] portfolio_kelly: optimizador falhou ({e}), usando Kelly fraccionário individual")
        stakes = [0.0] * n
        for i in active_idx:
            wp, odds = valid[i]
            stakes[i] = kelly_fraction(wp, odds, fraction=0.25)

    return stakes


def ev(win_prob, odds):
    """
    Expected Value por unidade apostada.

    Params:
        win_prob: probabilidade de vitória (0-1)
        odds: odds decimais

    Returns:
        float: EV por unidade (positivo = value bet)
    """
    if odds <= 0 or win_prob < 0 or win_prob > 1:
        return 0.0
    return float(win_prob * (odds - 1.0) - (1.0 - win_prob))


def roi_required(odds, n_bets=1):
    """
    Taxa de vitória de break-even para as odds dadas.

    Params:
        odds: odds decimais
        n_bets: número de apostas (não altera o break-even por aposta, mas é informativo)

    Returns:
        float: taxa de vitória mínima para ROI=0 (0-1)
    """
    if odds <= 1.0:
        return 1.0
    # Break-even: win_prob * (odds - 1) = (1 - win_prob)
    # win_prob * odds = 1
    # win_prob = 1 / odds
    return float(1.0 / odds)


def kelly_growth_rate(win_prob, odds, fraction=0.25):
    """
    Taxa de crescimento log-óptima (utilidade logarítmica) para Kelly fraccionário.

    Params:
        win_prob: probabilidade de vitória (0-1)
        odds: odds decimais
        fraction: fracção de Kelly a usar

    Returns:
        float: taxa de crescimento esperada por aposta (log-escala)
    """
    if win_prob <= 0 or win_prob >= 1 or odds <= 1:
        return 0.0

    stake = kelly_fraction(win_prob, odds, fraction)
    if stake <= 0:
        return 0.0

    b = odds - 1.0
    q = 1.0 - win_prob

    # E[log(1 + stake*b)] * win_prob + E[log(1 - stake)] * loss_prob
    gain = 1.0 + stake * b
    loss = 1.0 - stake

    if gain <= 0 or loss <= 0:
        return 0.0

    growth = win_prob * math.log(gain) + q * math.log(loss)
    return float(growth)


def stake_recommendation(win_prob, odds, bankroll=100.0, fraction=0.25, cap_pct=3.0):
    """
    Recomendação completa de stake.

    Params:
        win_prob: probabilidade de vitória (0-1)
        odds: odds decimais
        bankroll: banca total
        fraction: fracção de Kelly a usar
        cap_pct: limite máximo de stake como % de banca

    Returns:
        dict com:
            stake: valor em unidades de banca
            kelly_pct: percentagem Kelly fraccionário
            ev: expected value por unidade
            roi_required: taxa de vitória de break-even
            recommendation: string descritiva
    """
    kelly_pct = kelly_fraction(win_prob, odds, fraction)
    expected_value = ev(win_prob, odds)
    break_even = roi_required(odds)
    full_kelly = kelly_full(win_prob, odds)

    # Aplicar cap
    capped_pct = min(kelly_pct, cap_pct / 100.0)
    stake = bankroll * capped_pct

    # Gerar recomendação textual
    if expected_value <= 0:
        recommendation = "SEM VALUE — não apostar"
    elif full_kelly < 0.01:
        recommendation = "Edge marginal — evitar"
    elif full_kelly < 0.05:
        recommendation = "Edge pequeno — apostar com cautela"
    elif full_kelly < 0.15:
        recommendation = "Boa aposta — stake normal"
    else:
        recommendation = "Forte edge — stake máximo recomendado"

    if capped_pct < kelly_pct:
        recommendation += f" (cap aplicado: {cap_pct:.1f}%)"

    return {
        "stake": round(float(stake), 2),
        "kelly_pct": round(float(kelly_pct * 100), 3),
        "ev": round(float(expected_value), 4),
        "roi_required": round(float(break_even), 4),
        "recommendation": recommendation,
    }


def variance_of_strategy(win_prob, odds, n_bets, fraction=0.25):
    """
    Estatísticas de variância de uma estratégia de apostas.

    Params:
        win_prob: probabilidade de vitória (0-1)
        odds: odds decimais
        n_bets: número de apostas
        fraction: fracção de Kelly a usar

    Returns:
        dict com:
            expected_roi: ROI esperado por aposta
            std_roi: desvio padrão do ROI por aposta
            sharpe_approx: aproximação do rácio Sharpe
    """
    if win_prob <= 0 or win_prob >= 1 or odds <= 1 or n_bets <= 0:
        return {
            "expected_roi": 0.0,
            "std_roi": 0.0,
            "sharpe_approx": 0.0,
        }

    stake = kelly_fraction(win_prob, odds, fraction)
    b = odds - 1.0
    q = 1.0 - win_prob

    # ROI esperado por aposta = EV * stake
    # (como % de banca apostada)
    expected_roi_per_bet = ev(win_prob, odds) * stake

    # Variância do resultado por aposta
    # Var = p*(b*stake)^2 + q*(stake)^2 - (E[resultado])^2
    e_return = win_prob * (b * stake) + q * (-stake)
    e_return_sq = win_prob * (b * stake) ** 2 + q * (-stake) ** 2
    var_per_bet = e_return_sq - e_return ** 2
    std_per_bet = math.sqrt(max(0.0, var_per_bet))

    # Para n apostas independentes, a variância da soma escala com n
    # ROI total esperado
    total_expected_roi = expected_roi_per_bet * n_bets
    total_std = std_per_bet * math.sqrt(n_bets)

    # Sharpe aproximado: E[ROI] / Std[ROI] para sequência de n apostas
    sharpe = total_expected_roi / total_std if total_std > 0 else 0.0

    return {
        "expected_roi": round(float(expected_roi_per_bet), 6),
        "std_roi": round(float(std_per_bet), 6),
        "sharpe_approx": round(float(sharpe), 4),
    }
