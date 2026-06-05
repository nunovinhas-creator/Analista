# data_quality/label_quality.py — Análise de qualidade de labels (inspirado em Cleanlab)
# Detecta picks potencialmente mal-etiquetados comparando o outcome com a prob implícita nas odds.

import numpy as np
from utils import safe_float, wilson_ci


# ---------------------------------------------------------------------------
# Funções auxiliares internas
# ---------------------------------------------------------------------------

def _odds_implied_prob(pick):
    """Probabilidade implícita nas odds (overround não removido)."""
    odds = safe_float(pick.get("odds_over"))
    if odds > 1.01:
        return round(1.0 / odds, 4)
    return None


# ---------------------------------------------------------------------------
# Matriz de confusão estimada de erros de label
# ---------------------------------------------------------------------------

def compute_confidence_matrix(picks, predicted_probs=None):
    """Matriz de confusão 2×2 estimando a estrutura de erros de label.

    Linhas = label real (WIN=0, LOSS=1).
    Colunas = label previsto pelo modelo (WIN=0, LOSS=1).

    predicted_probs: lista de probabilidades previstas (uma por pick resolvido).
    Se None, usa probabilidade implícita nas odds (1/odds_over).

    Retorna np.ndarray shape (2, 2).
    """
    resolved = [p for p in picks if p.get("result_over25") in ("WIN", "LOSS")]
    if not resolved:
        return np.zeros((2, 2), dtype=int)

    matrix = np.zeros((2, 2), dtype=int)
    for i, p in enumerate(resolved):
        outcome = p["result_over25"]
        # Probabilidade prevista (WIN = classe 0)
        if predicted_probs is not None and i < len(predicted_probs):
            prob = float(predicted_probs[i])
        else:
            prob = _odds_implied_prob(p)
            if prob is None:
                continue  # sem odds válidas, ignorar

        label_row = 0 if outcome == "WIN" else 1          # linha = label real
        pred_col  = 0 if prob >= 0.5 else 1              # coluna = label previsto

        matrix[label_row][pred_col] += 1

    return matrix


# ---------------------------------------------------------------------------
# Score de erro de label individual
# ---------------------------------------------------------------------------

def label_error_score(predicted_prob, outcome, threshold=0.5):
    """Pontuação de confiança de que um label está ERRADO.

    Valores altos → maior suspeita de erro de label.

    Para WIN: error_score = 1 - predicted_prob
      (se prob alta prevê WIN e label é WIN, score baixo → label correcto)
    Para LOSS: error_score = predicted_prob
      (se prob alta prevê WIN mas label é LOSS, score alto → label suspeito)
    """
    if predicted_prob is None:
        return 0.0
    prob = float(predicted_prob)
    prob = max(0.0, min(1.0, prob))
    if outcome == "WIN":
        return round(1.0 - prob, 4)
    else:
        return round(prob, 4)


# ---------------------------------------------------------------------------
# Detecção de erros de label
# ---------------------------------------------------------------------------

def detect_label_errors(picks, threshold=0.3):
    """Encontra picks potencialmente mal-etiquetados.

    Um pick é suspeito se o error_score > threshold.
    Usa a probabilidade implícita nas odds como modelo de referência.

    Retorna lista de dicts: {pick, error_score, suspected_true_label, odds_implied_prob}.
    """
    errors = []
    for p in picks:
        if p.get("result_over25") not in ("WIN", "LOSS"):
            continue
        outcome = p["result_over25"]
        prob = _odds_implied_prob(p)
        if prob is None:
            continue

        score = label_error_score(prob, outcome)
        if score > threshold:
            suspected = "LOSS" if outcome == "WIN" else "WIN"
            errors.append({
                "pick":               p,
                "error_score":        score,
                "suspected_true_label": suspected,
                "odds_implied_prob":  prob,
            })

    # Ordenar por error_score descendente (mais suspeitos primeiro)
    errors.sort(key=lambda x: x["error_score"], reverse=True)
    return errors


# ---------------------------------------------------------------------------
# Relatório de qualidade
# ---------------------------------------------------------------------------

def quality_report(picks):
    """Relatório completo de qualidade das labels dos picks over25.

    Retorna dict com:
      n_total, n_resolved, n_suspected_errors, error_rate,
      suspicious_wins, suspicious_losses,
      class_imbalance, odds_calibration.
    """
    resolved = [p for p in picks if p.get("result_over25") in ("WIN", "LOSS")]
    wins_list  = [p for p in resolved if p["result_over25"] == "WIN"]
    losses_list = [p for p in resolved if p["result_over25"] == "LOSS"]

    n_total    = len(picks)
    n_resolved = len(resolved)

    # Erros suspeitos
    suspected = detect_label_errors(picks, threshold=0.3)
    suspicious_wins   = [e for e in suspected if e["pick"]["result_over25"] == "WIN"]
    suspicious_losses = [e for e in suspected if e["pick"]["result_over25"] == "LOSS"]

    n_errors   = len(suspected)
    error_rate = round(n_errors / n_resolved, 4) if n_resolved else 0.0

    # Desequilíbrio de classes
    pct_wins   = round(len(wins_list)   / n_resolved, 4) if n_resolved else 0.0
    pct_losses = round(len(losses_list) / n_resolved, 4) if n_resolved else 0.0
    class_imbalance = {
        "n_wins":     len(wins_list),
        "n_losses":   len(losses_list),
        "pct_wins":   pct_wins,
        "pct_losses": pct_losses,
    }

    # Calibração das odds
    implied_probs = []
    actual_outcomes = []
    for p in resolved:
        prob = _odds_implied_prob(p)
        if prob is not None:
            implied_probs.append(prob)
            actual_outcomes.append(1 if p["result_over25"] == "WIN" else 0)

    if implied_probs:
        mean_implied = round(float(np.mean(implied_probs)), 4)
        actual_wr    = round(float(np.mean(actual_outcomes)), 4)
        calib_error  = round(abs(mean_implied - actual_wr), 4)
    else:
        mean_implied = 0.0
        actual_wr    = 0.0
        calib_error  = 0.0

    odds_calibration = {
        "mean_implied_prob": mean_implied,
        "actual_win_rate":   actual_wr,
        "calibration_error": calib_error,
        "n_with_odds":       len(implied_probs),
    }

    return {
        "n_total":             n_total,
        "n_resolved":          n_resolved,
        "n_suspected_errors":  n_errors,
        "error_rate":          error_rate,
        "suspicious_wins":     suspicious_wins,
        "suspicious_losses":   suspicious_losses,
        "class_imbalance":     class_imbalance,
        "odds_calibration":    odds_calibration,
    }


# ---------------------------------------------------------------------------
# Filtro de picks de alta qualidade
# ---------------------------------------------------------------------------

def filter_high_quality(picks, min_confidence=0.6):
    """Devolve apenas picks onde a confiança de label >= threshold.

    Confiança = 1 - error_score. Picks sem odds são incluídos por defeito.
    """
    result = []
    for p in picks:
        prob = _odds_implied_prob(p)
        if prob is None:
            # Sem odds: não podemos avaliar, inclui por defeito
            result.append(p)
            continue
        outcome = p.get("result_over25")
        if outcome not in ("WIN", "LOSS"):
            # Pendente: inclui sempre
            result.append(p)
            continue
        score     = label_error_score(prob, outcome)
        confidence = 1.0 - score
        if confidence >= min_confidence:
            result.append(p)
    return result
