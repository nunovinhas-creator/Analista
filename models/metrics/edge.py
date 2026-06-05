"""
Métricas de qualidade de edge e value para análise de apostas desportivas.
"""

import math
from collections import defaultdict
from scipy.stats import norm


def clv(odds_open, odds_close):
    """
    Closing Line Value: mede a qualidade da aposta em relação às odds de fecho.
    CLV positivo indica que as odds de abertura eram melhores do que as de fecho.

    Params:
        odds_open: odds na abertura (decimal)
        odds_close: odds no fecho de mercado (decimal)

    Returns:
        float: CLV como percentagem (ex. 2.5 significa 2.5% de edge sobre o fecho)
    """
    if odds_open <= 1.0 or odds_close <= 1.0:
        return 0.0
    # CLV = (prob_close - prob_open) / prob_open * 100
    # prob = 1 / odds
    prob_open = 1.0 / odds_open
    prob_close = 1.0 / odds_close
    if prob_open <= 0:
        return 0.0
    return float((prob_close - prob_open) / prob_open * 100.0)


def clv_series(picks):
    """
    Calcula CLV para uma série de picks do over25-scanner.
    Se não houver campo de odds de fecho, retorna None para esse pick.

    Params:
        picks: lista de dicts com campos do picks.json (over25-scanner)
               Espera campo "odds_over" (abertura) e opcionalmente "odds_close"

    Returns:
        dict com:
            values: lista de CLV por pick (None se não disponível)
            mean: média dos CLV disponíveis
            std: desvio padrão dos CLV disponíveis
            positive_pct: percentagem com CLV positivo
            n: número de picks com CLV calculado
    """
    values = []
    computed = []

    for pick in picks:
        try:
            odds_open = float(pick.get("odds_over", 0) or 0)
        except (ValueError, TypeError):
            odds_open = 0.0

        # Tentar campo de odds de fecho (pode não existir)
        odds_close_raw = pick.get("odds_close") or pick.get("closing_odds")
        if odds_close_raw is None:
            values.append(None)
            continue

        try:
            odds_close = float(odds_close_raw)
        except (ValueError, TypeError):
            values.append(None)
            continue

        if odds_open <= 1.0 or odds_close <= 1.0:
            values.append(None)
            continue

        clv_val = clv(odds_open, odds_close)
        values.append(clv_val)
        computed.append(clv_val)

    if not computed:
        return {
            "values": values,
            "mean": None,
            "std": None,
            "positive_pct": None,
            "n": 0,
        }

    n = len(computed)
    mean_clv = sum(computed) / n
    variance = sum((v - mean_clv) ** 2 for v in computed) / max(1, n - 1)
    std_clv = math.sqrt(variance)
    positive_pct = sum(1 for v in computed if v > 0) / n * 100.0

    return {
        "values": values,
        "mean": round(float(mean_clv), 4),
        "std": round(float(std_clv), 4),
        "positive_pct": round(float(positive_pct), 2),
        "n": n,
    }


def expected_value(win_prob, odds):
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


def edge_significance_test(wins, total, break_even_prob):
    """
    Teste de significância estatística do edge (H0: win_rate == break_even).

    Params:
        wins: número de vitórias
        total: número total de apostas
        break_even_prob: probabilidade de break-even (1/odds médias)

    Returns:
        dict com:
            pvalue: p-valor do teste z unilateral
            z_score: z-score observado
            significant_05: bool, se p < 0.05
            significant_01: bool, se p < 0.01
            required_n_for_significance: n mínimo para atingir significância 0.05
    """
    if total <= 0 or break_even_prob <= 0 or break_even_prob >= 1:
        return {
            "pvalue": 1.0,
            "z_score": 0.0,
            "significant_05": False,
            "significant_01": False,
            "required_n_for_significance": None,
        }

    win_rate = wins / total
    # Teste z para proporções: H0: p = p0
    std_err = math.sqrt(break_even_prob * (1.0 - break_even_prob) / total)
    if std_err <= 0:
        z = 0.0
    else:
        z = (win_rate - break_even_prob) / std_err

    # p-valor unilateral (H1: win_rate > break_even)
    p_value = float(1.0 - norm.cdf(z))

    # N mínimo para detectar o edge observado com 80% de poder e alpha=0.05
    # z_alpha = 1.645 (5% unilateral), z_beta = 0.842 (80% poder)
    if win_rate > break_even_prob:
        effect_size = win_rate - break_even_prob
        z_alpha = 1.645
        z_beta = 0.842
        p0 = break_even_prob
        p1 = win_rate
        # Fórmula de amostragem para teste de proporções
        num = (z_alpha * math.sqrt(p0 * (1 - p0)) + z_beta * math.sqrt(p1 * (1 - p1))) ** 2
        req_n = int(math.ceil(num / (effect_size ** 2)))
    else:
        req_n = None

    return {
        "pvalue": round(float(p_value), 6),
        "z_score": round(float(z), 4),
        "significant_05": bool(p_value < 0.05),
        "significant_01": bool(p_value < 0.01),
        "required_n_for_significance": req_n,
    }


def roi_decomposition(picks, odds_key="odds_over"):
    """
    Decomposição do ROI por várias dimensões.
    Apenas considera picks com resultado definido (WIN/LOSS).

    Params:
        picks: lista de dicts do picks.json (over25-scanner)
        odds_key: chave das odds

    Returns:
        dict com:
            total_roi: ROI total (%)
            roi_by_month: dict mês (YYYY-MM) -> ROI
            roi_by_movement: dict "SHORTENING"/"DRIFTING" -> ROI
            roi_by_league: dict liga -> ROI
            roi_by_score_band: dict banda de score_sistema -> ROI
    """
    def compute_roi(filtered_picks):
        """Calcula ROI para uma sublista de picks com resultado."""
        if not filtered_picks:
            return None
        total_staked = 0.0
        total_returned = 0.0
        for p in filtered_picks:
            try:
                odds = float(p.get(odds_key, 0) or 0)
            except (ValueError, TypeError):
                odds = 0.0
            result = p.get("result_over25", None)
            if result not in ("WIN", "LOSS") or odds <= 1.0:
                continue
            total_staked += 1.0
            if result == "WIN":
                total_returned += odds
        if total_staked == 0:
            return None
        return round(((total_returned - total_staked) / total_staked) * 100.0, 2)

    # Filtrar picks com resultado
    resolved = [p for p in picks if p.get("result_over25") in ("WIN", "LOSS")]

    total_roi = compute_roi(resolved)

    # Por mês
    by_month = defaultdict(list)
    for p in resolved:
        date_str = p.get("data", "") or ""
        month = date_str[:7] if len(date_str) >= 7 else "unknown"
        by_month[month].append(p)
    roi_by_month = {m: compute_roi(ps) for m, ps in sorted(by_month.items())}

    # Por movimento
    by_movement = defaultdict(list)
    for p in resolved:
        mov = p.get("movimento", "unknown") or "unknown"
        by_movement[mov].append(p)
    roi_by_movement = {m: compute_roi(ps) for m, ps in by_movement.items()}

    # Por liga
    by_league = defaultdict(list)
    for p in resolved:
        liga = p.get("liga", "unknown") or "unknown"
        by_league[liga].append(p)
    roi_by_league = {l: compute_roi(ps) for l, ps in by_league.items()}

    # Por banda de score_sistema (0-25, 25-50, 50-75, 75-100)
    def score_band(score):
        try:
            s = int(float(score))
        except (ValueError, TypeError):
            return "unknown"
        if s < 25:
            return "0-24"
        elif s < 50:
            return "25-49"
        elif s < 75:
            return "50-74"
        else:
            return "75-100"

    by_score = defaultdict(list)
    for p in resolved:
        band = score_band(p.get("score_sistema", 0))
        by_score[band].append(p)
    roi_by_score_band = {b: compute_roi(ps) for b, ps in sorted(by_score.items())}

    return {
        "total_roi": total_roi,
        "roi_by_month": roi_by_month,
        "roi_by_movement": roi_by_movement,
        "roi_by_league": roi_by_league,
        "roi_by_score_band": roi_by_score_band,
    }


def sharp_money_indicator(picks):
    """
    Indicador de sharp money: compara ROI de SHORTENING vs DRIFTING.
    Movimento SHORTENING significa que os sharps estão a apostar (odds a descer).

    Params:
        picks: lista de dicts do picks.json (over25-scanner)

    Returns:
        dict com:
            shortening_roi: ROI dos picks com movimento SHORTENING
            drifting_roi: ROI dos picks com movimento DRIFTING
            shortening_n: número de picks SHORTENING com resultado
            drifting_n: número de picks DRIFTING com resultado
            sharp_edge: diferença de ROI (SHORTENING - DRIFTING)
    """
    shortening = []
    drifting = []

    for p in picks:
        result = p.get("result_over25")
        if result not in ("WIN", "LOSS"):
            continue
        mov = (p.get("movimento") or "").upper()
        if mov == "SHORTENING":
            shortening.append(p)
        elif mov == "DRIFTING":
            drifting.append(p)

    def roi_from_list(lst):
        if not lst:
            return None
        staked = 0.0
        returned = 0.0
        for p in lst:
            try:
                odds = float(p.get("odds_over", 0) or 0)
            except (ValueError, TypeError):
                odds = 0.0
            if odds <= 1.0:
                continue
            staked += 1.0
            if p.get("result_over25") == "WIN":
                returned += odds
        if staked == 0:
            return None
        return round((returned - staked) / staked * 100.0, 2)

    s_roi = roi_from_list(shortening)
    d_roi = roi_from_list(drifting)

    if s_roi is not None and d_roi is not None:
        sharp_edge = round(s_roi - d_roi, 2)
    elif s_roi is not None:
        sharp_edge = s_roi
    elif d_roi is not None:
        sharp_edge = -d_roi
    else:
        sharp_edge = None

    return {
        "shortening_roi": s_roi,
        "drifting_roi": d_roi,
        "shortening_n": len(shortening),
        "drifting_n": len(drifting),
        "sharp_edge": sharp_edge,
    }


def drawdown_analysis(cum_roi_series):
    """
    Análise de drawdown de uma série de ROI acumulado.

    Params:
        cum_roi_series: lista de floats representando ROI acumulado ao longo do tempo

    Returns:
        dict com:
            max_drawdown: máximo drawdown absoluto (em unidades de ROI)
            max_drawdown_pct: máximo drawdown como percentagem do pico
            recovery_periods: lista de dicts com start, trough, end, depth
            current_drawdown: drawdown actual a partir do último pico
    """
    if not cum_roi_series or len(cum_roi_series) < 2:
        return {
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "recovery_periods": [],
            "current_drawdown": 0.0,
        }

    series = [float(v) for v in cum_roi_series]
    n = len(series)

    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    recovery_periods = []

    peak = series[0]
    peak_idx = 0
    in_drawdown = False
    trough_val = series[0]
    trough_idx = 0

    for i in range(1, n):
        val = series[i]
        if val > peak:
            # Novo pico — fechar drawdown anterior se existia
            if in_drawdown:
                # Recuperação completa (pode não ter chegado a completar)
                depth = peak - trough_val
                recovery_periods.append({
                    "start": peak_idx,
                    "trough": trough_idx,
                    "end": i,
                    "depth": round(depth, 4),
                })
                in_drawdown = False
            peak = val
            peak_idx = i
            trough_val = val
        else:
            # Abaixo do pico
            if val < trough_val:
                trough_val = val
                trough_idx = i
                in_drawdown = True

            current_dd = peak - val
            current_dd_pct = (current_dd / abs(peak)) * 100.0 if peak != 0 else 0.0

            if current_dd > max_drawdown:
                max_drawdown = current_dd
                max_drawdown_pct = current_dd_pct

    # Drawdown actual (a partir do último pico até ao fim)
    current_drawdown = float(peak - series[-1]) if series[-1] < peak else 0.0

    return {
        "max_drawdown": round(float(max_drawdown), 4),
        "max_drawdown_pct": round(float(max_drawdown_pct), 4),
        "recovery_periods": recovery_periods,
        "current_drawdown": round(float(current_drawdown), 4),
    }


def kelly_optimal_fraction(wins, total, avg_odds):
    """
    Fracção de Kelly empiricamente óptima com base no histórico.
    Usa a fórmula de Kelly com a win rate observada.

    Params:
        wins: número de vitórias observadas
        total: número total de apostas
        avg_odds: odds médias das apostas

    Returns:
        float: fracção de Kelly recomendada (0-1)
    """
    if total <= 0 or avg_odds <= 1.0:
        return 0.0

    win_rate = wins / total
    b = avg_odds - 1.0
    q = 1.0 - win_rate

    kelly = (b * win_rate - q) / b
    return float(max(0.0, kelly))
