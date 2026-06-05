# data_quality/drift.py — Detecção de data drift (inspirado no EvidentlyAI)
# Monitoriza distribuições de odds, xG, score_sistema e win_rate ao longo do tempo.

import numpy as np
from scipy import stats as scipy_stats
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# PSI — Population Stability Index
# ---------------------------------------------------------------------------

def psi(expected, actual, bins=10, eps=1e-6):
    """Population Stability Index entre duas distribuições.

    PSI < 0.1  → estável (sem mudança significativa)
    0.1–0.2    → deriva moderada
    > 0.2      → deriva significativa

    Suporta dados contínuos (auto-binning) e categóricos (arrays de strings/ints discretos).
    Retorna float. Trata amostras vazias ou muito pequenas com segurança.
    """
    if not expected or not actual:
        return 0.0

    expected_arr = np.array([v for v in expected if v is not None and not (isinstance(v, float) and np.isnan(v))], dtype=float)
    actual_arr   = np.array([v for v in actual   if v is not None and not (isinstance(v, float) and np.isnan(v))], dtype=float)

    if len(expected_arr) == 0 or len(actual_arr) == 0:
        return 0.0

    # Determinar bins: usar quantis da distribuição esperada para bins iguais
    n_bins = min(bins, max(2, len(np.unique(expected_arr))))
    breakpoints = np.percentile(expected_arr, np.linspace(0, 100, n_bins + 1))
    # Garantir uniqueness para np.digitize
    breakpoints = np.unique(breakpoints)
    if len(breakpoints) < 2:
        return 0.0

    # Histogramas normalizados
    expected_counts, _ = np.histogram(expected_arr, bins=breakpoints)
    actual_counts, _   = np.histogram(actual_arr,   bins=breakpoints)

    expected_pct = expected_counts / (len(expected_arr) + eps)
    actual_pct   = actual_counts   / (len(actual_arr)   + eps)

    # Substituir zeros por eps para evitar log(0)
    expected_pct = np.where(expected_pct == 0, eps, expected_pct)
    actual_pct   = np.where(actual_pct   == 0, eps, actual_pct)

    psi_value = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(round(psi_value, 4))


def psi_interpretation(psi_value):
    """Interpreta o valor de PSI.

    Retorna: "stable" | "moderate_drift" | "significant_drift"
    """
    if psi_value < 0.1:
        return "stable"
    elif psi_value < 0.2:
        return "moderate_drift"
    return "significant_drift"


# ---------------------------------------------------------------------------
# KS Test — Kolmogorov-Smirnov para duas amostras
# ---------------------------------------------------------------------------

def ks_test(sample1, sample2):
    """Teste KS de duas amostras para detectar drift em distribuições contínuas.

    Retorna dict com:
      statistic  float   — estatística KS (distância máxima entre CDFs)
      pvalue     float   — p-value do teste
      drifted    bool    — True se pvalue < 0.05
    """
    s1 = [v for v in sample1 if v is not None and not (isinstance(v, float) and np.isnan(v))]
    s2 = [v for v in sample2 if v is not None and not (isinstance(v, float) and np.isnan(v))]

    if len(s1) < 2 or len(s2) < 2:
        return {"statistic": 0.0, "pvalue": 1.0, "drifted": False}

    result = scipy_stats.ks_2samp(s1, s2)
    return {
        "statistic": float(round(result.statistic, 4)),
        "pvalue":    float(round(result.pvalue, 4)),
        "drifted":   bool(result.pvalue < 0.05),
    }


# ---------------------------------------------------------------------------
# Chi-squared test — drift em distribuições categóricas
# ---------------------------------------------------------------------------

def chi2_drift_test(cat_dist_before, cat_dist_after):
    """Teste qui-quadrado para detectar drift em distribuições categóricas.

    cat_dist_before / cat_dist_after: dict {categoria: contagem}
    Retorna dict com: statistic, pvalue, drifted
    """
    if not cat_dist_before or not cat_dist_after:
        return {"statistic": 0.0, "pvalue": 1.0, "drifted": False}

    all_cats = sorted(set(list(cat_dist_before.keys()) + list(cat_dist_after.keys())))
    obs_before = np.array([cat_dist_before.get(c, 0) for c in all_cats], dtype=float)
    obs_after  = np.array([cat_dist_after.get(c, 0)  for c in all_cats], dtype=float)

    # Precisamos de pelo menos 2 categorias e contagens não-nulas
    if len(all_cats) < 2 or obs_before.sum() == 0 or obs_after.sum() == 0:
        return {"statistic": 0.0, "pvalue": 1.0, "drifted": False}

    # Normalizar 'before' como distribuição esperada para a dimensão de 'after'
    expected = obs_before / obs_before.sum() * obs_after.sum()
    # Evitar bins com expected=0
    mask = expected > 0
    if mask.sum() < 2:
        return {"statistic": 0.0, "pvalue": 1.0, "drifted": False}

    try:
        stat, pvalue = scipy_stats.chisquare(obs_after[mask], f_exp=expected[mask])
    except Exception:
        return {"statistic": 0.0, "pvalue": 1.0, "drifted": False}

    return {
        "statistic": float(round(stat, 4)),
        "pvalue":    float(round(pvalue, 4)),
        "drifted":   bool(pvalue < 0.05),
    }


# ---------------------------------------------------------------------------
# DriftMonitor — classe principal de monitorização
# ---------------------------------------------------------------------------

class DriftMonitor:
    """Monitoriza drift em distribuições de features dos picks Over 2.5.

    Utiliza PSI para features contínuas e KS test como validação adicional.
    Também detecta concept drift no win_rate via CUSUM.
    """

    def __init__(self, reference_window=30, detection_window=14):
        self.reference_window  = reference_window
        self.detection_window  = detection_window
        self._ref_odds         = []
        self._ref_xg           = []
        self._ref_score        = []
        self._ref_mov_dist     = {}
        self._baseline_wr      = None
        self._fitted           = False

    # ------------------------------------------------------------------
    def fit(self, picks):
        """Ajusta o monitor com os picks de referência (últimos N resolvidos).

        picks: lista de picks raw (dicts do over25-scanner).
        Usa os últimos self.reference_window picks resolvidos como baseline.
        """
        resolved = [p for p in picks if p.get("result_over25") in ("WIN", "LOSS")]
        ref = resolved[-self.reference_window:] if len(resolved) >= self.reference_window else resolved

        self._ref_odds  = [_safe_num(p.get("odds_over"))  for p in ref if _safe_num(p.get("odds_over"))  is not None]
        self._ref_xg    = [_safe_num(p.get("xg_total"))   for p in ref if _safe_num(p.get("xg_total"))   is not None]
        self._ref_score = [_safe_num(p.get("score_sistema")) for p in ref if _safe_num(p.get("score_sistema")) is not None]

        # Distribuição categórica de movimento
        self._ref_mov_dist = {}
        for p in ref:
            mov = p.get("movimento") or "UNKNOWN"
            self._ref_mov_dist[mov] = self._ref_mov_dist.get(mov, 0) + 1

        wins = sum(1 for p in ref if p.get("result_over25") == "WIN")
        self._baseline_wr = wins / len(ref) if ref else None
        self._fitted = True

    # ------------------------------------------------------------------
    def detect(self, picks):
        """Compara distribuições actuais vs baseline.

        picks: lista de picks recentes (todos, incluindo não resolvidos).
        Retorna dict com drift_detected, psi_score, psi_odds, psi_xg,
        psi_score_sistema, ks_result, alerts, summary.
        """
        if not self._fitted:
            self.fit(picks)

        # Janela de detecção: picks mais recentes
        recent = picks[-self.detection_window:] if len(picks) >= self.detection_window else picks

        cur_odds  = [_safe_num(p.get("odds_over"))     for p in recent if _safe_num(p.get("odds_over"))     is not None]
        cur_xg    = [_safe_num(p.get("xg_total"))      for p in recent if _safe_num(p.get("xg_total"))      is not None]
        cur_score = [_safe_num(p.get("score_sistema")) for p in recent if _safe_num(p.get("score_sistema")) is not None]

        cur_mov_dist = {}
        for p in recent:
            mov = p.get("movimento") or "UNKNOWN"
            cur_mov_dist[mov] = cur_mov_dist.get(mov, 0) + 1

        psi_odds  = psi(self._ref_odds,  cur_odds)
        psi_xg    = psi(self._ref_xg,    cur_xg)
        psi_score = psi(self._ref_score, cur_score)

        ks_result = ks_test(self._ref_odds, cur_odds)
        chi2_mov  = chi2_drift_test(self._ref_mov_dist, cur_mov_dist)

        # Score composto (média ponderada PSI)
        psi_values = [v for v in [psi_odds, psi_xg, psi_score] if v > 0]
        psi_composite = float(np.mean(psi_values)) if psi_values else 0.0

        alerts = []
        if psi_interpretation(psi_odds)  != "stable":
            alerts.append(f"[DRIFT] Odds PSI={psi_odds:.3f} ({psi_interpretation(psi_odds)})")
        if psi_interpretation(psi_xg)    != "stable":
            alerts.append(f"[DRIFT] xG PSI={psi_xg:.3f} ({psi_interpretation(psi_xg)})")
        if psi_interpretation(psi_score) != "stable":
            alerts.append(f"[DRIFT] Score PSI={psi_score:.3f} ({psi_interpretation(psi_score)})")
        if ks_result["drifted"]:
            alerts.append(f"[DRIFT] KS test odds p={ks_result['pvalue']:.3f} — distribuição alterada")
        if chi2_mov["drifted"]:
            alerts.append(f"[DRIFT] Chi2 movimento p={chi2_mov['pvalue']:.3f} — mix SHORTENING/DRIFTING alterado")

        drift_detected = len(alerts) > 0

        if not drift_detected:
            summary = "Sem drift detectado — distribuições estáveis."
        elif psi_composite >= 0.2:
            summary = f"Drift significativo detectado (PSI composto={psi_composite:.3f}). Rever pipeline de picks."
        else:
            summary = f"Deriva moderada detectada (PSI composto={psi_composite:.3f}). Monitorizar evolução."

        return {
            "drift_detected":    drift_detected,
            "psi_score":         psi_composite,
            "psi_odds":          psi_odds,
            "psi_xg":            psi_xg,
            "psi_score_sistema": psi_score,
            "ks_result":         ks_result,
            "chi2_movement":     chi2_mov,
            "alerts":            alerts,
            "summary":           summary,
        }

    # ------------------------------------------------------------------
    def detect_concept_drift(self, resolved_picks, window=20):
        """Detecta concept drift no win_rate via CUSUM sequencial.

        CUSUM (Cumulative Sum Control Chart) acumula desvios em relação ao baseline.
        Um change_point é sinalizado quando a soma cumulativa excede um limiar.

        Retorna dict com: drift_detected, cusum_series, change_point (int or None),
        current_wr, baseline_wr.
        """
        picks = [p for p in resolved_picks if p.get("result_over25") in ("WIN", "LOSS")]

        if len(picks) < window:
            return {
                "drift_detected": False,
                "cusum_series":   [],
                "change_point":   None,
                "current_wr":     None,
                "baseline_wr":    self._baseline_wr,
            }

        baseline = self._baseline_wr
        if baseline is None:
            wins_ref = sum(1 for p in picks[:window] if p["result_over25"] == "WIN")
            baseline = wins_ref / window

        # Parâmetros CUSUM: allowance k = metade da diferença mínima a detectar
        k = 0.10  # detecta desvio de ~10 pp no WR
        h = 3.0   # limiar de alarme (múltiplo do desvio padrão)

        cusum_pos = 0.0
        cusum_neg = 0.0
        cusum_series = []
        change_point = None

        for i, p in enumerate(picks):
            x = 1.0 if p["result_over25"] == "WIN" else 0.0
            cusum_pos = max(0.0, cusum_pos + (x - baseline) - k)
            cusum_neg = max(0.0, cusum_neg - (x - baseline) - k)
            cusum_val = max(cusum_pos, cusum_neg)
            cusum_series.append(round(cusum_val, 4))
            if cusum_val >= h and change_point is None:
                change_point = i

        recent_picks = picks[-window:]
        current_wr = sum(1 for p in recent_picks if p["result_over25"] == "WIN") / len(recent_picks)

        drift_detected = change_point is not None

        return {
            "drift_detected": drift_detected,
            "cusum_series":   cusum_series,
            "change_point":   change_point,
            "current_wr":     round(current_wr, 4),
            "baseline_wr":    round(baseline, 4) if baseline else None,
        }


# ---------------------------------------------------------------------------
# run_drift_analysis — ponto de entrada para o monitor
# ---------------------------------------------------------------------------

def run_drift_analysis(over25_stats):
    """Análise completa de drift usando o output de analyze_over25.

    over25_stats: dict retornado por analyze_over25().
    Retorna dict com resultados de drift e concept drift.
    """
    # Reconstruir picks raw a partir das stats disponíveis
    all_picks = over25_stats.get("all_picks_raw", [])

    monitor = DriftMonitor(reference_window=30, detection_window=14)
    monitor.fit(all_picks)
    drift_result = monitor.detect(all_picks)

    # Concept drift via CUSUM
    concept_result = monitor.detect_concept_drift(all_picks, window=20)

    # Alertas adicionais de concept drift
    if concept_result["drift_detected"]:
        cp = concept_result["change_point"]
        cwr = concept_result["current_wr"]
        bwr = concept_result["baseline_wr"]
        drift_result["alerts"].append(
            f"[CONCEPT DRIFT] Win rate mudou: baseline={bwr:.1%} → actual={cwr:.1%} (change point em pick #{cp})"
        )

    return {
        "drift":         drift_result,
        "concept_drift": concept_result,
        "n_reference":   len([p for p in all_picks if p.get("result_over25") in ("WIN", "LOSS")]),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Utilitário interno
# ---------------------------------------------------------------------------

def _safe_num(v, default=None):
    """Converte para float; retorna default se inválido."""
    if v is None or v == "":
        return default
    try:
        f = float(v)
        return f if np.isfinite(f) else default
    except (ValueError, TypeError):
        return default
