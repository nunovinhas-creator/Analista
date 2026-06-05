"""
Métricas de calibração estatística para previsões probabilísticas.
"""

import math


def brier_score(y_true, y_pred):
    """
    Brier Score: erro quadrático médio das previsões de probabilidade.
    Valores mais baixos indicam melhor calibração.

    Params:
        y_true: lista de valores observados (0 ou 1)
        y_pred: lista de probabilidades previstas (0-1)

    Returns:
        float: Brier Score (0 = perfeito, 1 = terrível)
    """
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return None

    n = len(y_true)
    total = sum((float(p) - float(t)) ** 2 for t, p in zip(y_true, y_pred))
    return float(total / n)


def log_loss_score(y_true, y_pred, eps=1e-7):
    """
    Log Loss (cross-entropy) para previsões probabilísticas.
    Penaliza fortemente previsões confiantes mas erradas.

    Params:
        y_true: lista de valores observados (0 ou 1)
        y_pred: lista de probabilidades previstas (0-1)
        eps: valor de clipping para evitar log(0)

    Returns:
        float: Log Loss (menor = melhor)
    """
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return None

    n = len(y_true)
    total = 0.0
    for t, p in zip(y_true, y_pred):
        p_clipped = max(eps, min(1.0 - eps, float(p)))
        t_val = float(t)
        total += -(t_val * math.log(p_clipped) + (1.0 - t_val) * math.log(1.0 - p_clipped))

    return float(total / n)


def reliability_diagram_data(y_true, y_pred, n_bins=10):
    """
    Dados para o diagrama de fiabilidade (reliability diagram).
    Agrupa as previsões em bins e compara frequência prevista vs observada.

    Params:
        y_true: lista de valores observados (0 ou 1)
        y_pred: lista de probabilidades previstas (0-1)
        n_bins: número de bins de calibração

    Returns:
        lista de dicts com:
            bin_center: centro do bin
            predicted_mean: média das probabilidades no bin
            actual_freq: frequência real de eventos positivos no bin
            n: número de amostras no bin
            calibration_error: |predicted_mean - actual_freq|
    """
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return []

    bin_size = 1.0 / n_bins
    bins = [{"preds": [], "trues": []} for _ in range(n_bins)]

    for t, p in zip(y_true, y_pred):
        p_val = float(max(0.0, min(1.0, p)))
        bin_idx = min(int(p_val / bin_size), n_bins - 1)
        bins[bin_idx]["preds"].append(p_val)
        bins[bin_idx]["trues"].append(float(t))

    result = []
    for i, b in enumerate(bins):
        center = (i + 0.5) * bin_size
        n = len(b["preds"])
        if n == 0:
            continue
        pred_mean = sum(b["preds"]) / n
        actual_freq = sum(b["trues"]) / n
        cal_error = abs(pred_mean - actual_freq)
        result.append({
            "bin_center": round(center, 4),
            "predicted_mean": round(pred_mean, 4),
            "actual_freq": round(actual_freq, 4),
            "n": n,
            "calibration_error": round(cal_error, 4),
        })

    return result


def expected_calibration_error(y_true, y_pred, n_bins=10):
    """
    Expected Calibration Error (ECE): média ponderada dos erros de calibração por bin.

    Params:
        y_true: lista de valores observados (0 ou 1)
        y_pred: lista de probabilidades previstas (0-1)
        n_bins: número de bins

    Returns:
        float: ECE (0 = calibração perfeita)
    """
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return 0.0

    n_total = len(y_true)
    diagram = reliability_diagram_data(y_true, y_pred, n_bins)

    if not diagram:
        return 0.0

    ece = sum(d["calibration_error"] * d["n"] / n_total for d in diagram)
    return float(ece)


def calibration_from_records(records, prob_key, hit_key, scale=100.0):
    """
    Calcula métricas de calibração a partir de registos do history.json.

    Params:
        records: lista de dicts com campos do history.json
        prob_key: campo de probabilidade, ex. "po" (over 2.5) ou "pb" (BTTS)
                  — valores em escala 0-100 por defeito
        hit_key: campo binário de resultado, ex. "hit_o25" ou "hit_btts"
        scale: factor de escala das probabilidades (100.0 para campos 0-100)

    Returns:
        dict com:
            brier: Brier Score
            log_loss: Log Loss
            ece: Expected Calibration Error
            reliability_diagram: lista de dicts para diagrama
            n: número de amostras usadas
    """
    y_true = []
    y_pred = []

    for rec in records:
        prob_raw = rec.get(prob_key)
        hit_raw = rec.get(hit_key)

        # Ignorar registos sem dados
        if prob_raw is None or hit_raw is None:
            continue

        try:
            prob_val = float(prob_raw) / scale
            hit_val = 1.0 if hit_raw else 0.0
        except (ValueError, TypeError):
            continue

        # Validar intervalo
        if not (0.0 <= prob_val <= 1.0):
            continue

        y_pred.append(prob_val)
        y_true.append(hit_val)

    if not y_true:
        return {
            "brier": None,
            "log_loss": None,
            "ece": None,
            "reliability_diagram": [],
            "n": 0,
        }

    bs = brier_score(y_true, y_pred)
    ll = log_loss_score(y_true, y_pred)
    return {
        "brier": round(bs, 6) if bs is not None else None,
        "log_loss": round(ll, 6) if ll is not None else None,
        "ece": round(expected_calibration_error(y_true, y_pred), 6),
        "reliability_diagram": reliability_diagram_data(y_true, y_pred),
        "n": len(y_true),
    }


def sharpness(y_pred):
    """
    Sharpness: medida da concentração das previsões (quão extremas são).
    Calculada como E[p*(1-p)] — menor valor indica previsões mais "afiadas" (extremas).

    Params:
        y_pred: lista de probabilidades previstas (0-1)

    Returns:
        float: sharpness (0 = todas as previsões são 0 ou 1; 0.25 = todas são 0.5)
    """
    if not y_pred:
        return 0.0
    n = len(y_pred)
    total = sum(float(p) * (1.0 - float(p)) for p in y_pred)
    return float(total / n)


def resolution(y_true, y_pred):
    """
    Resolução: variância das médias condicionais em relação à taxa base.
    Maior resolução indica previsões mais informativas.

    Params:
        y_true: lista de valores observados (0 ou 1)
        y_pred: lista de probabilidades previstas (0-1)

    Returns:
        float: resolução (maior = melhor)
    """
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return 0.0

    n = len(y_true)
    base_rate = sum(float(t) for t in y_true) / n

    if base_rate == 0.0 or base_rate == 1.0:
        return 0.0

    # Agrupar em bins para calcular médias condicionais
    n_bins = min(10, max(2, n // 10))
    bin_size = 1.0 / n_bins
    bins = {}

    for t, p in zip(y_true, y_pred):
        p_val = float(max(0.0, min(1.0 - 1e-9, p)))
        bin_idx = int(p_val / bin_size)
        if bin_idx not in bins:
            bins[bin_idx] = []
        bins[bin_idx].append(float(t))

    # Variância ponderada das médias condicionais
    res = 0.0
    for bin_vals in bins.values():
        n_b = len(bin_vals)
        if n_b == 0:
            continue
        cond_mean = sum(bin_vals) / n_b
        res += (n_b / n) * (cond_mean - base_rate) ** 2

    return float(res)
