# analyze_football.py — Métricas e análise do football-dashboard (Matemática Da Bola)
from datetime import datetime, timezone, timedelta
from utils import wilson_ci, parse_date, segment_stats


def _brier_score(records, prob_key, hit_key):
    """Brier Score: qualidade de calibração (0=perfeito, 0.25=aleatório).
    prob_key armazena probabilidade em escala 0-100 (ex: 71.0 = 71%).
    """
    scores = []
    for r in records:
        prob = r.get(prob_key)
        hit  = r.get(hit_key)
        if prob is not None and hit is not None:
            try:
                p = float(prob) / 100.0  # converter 0-100 → 0-1
                scores.append((p - (1 if hit else 0)) ** 2)
            except (ValueError, TypeError):
                pass
    return round(sum(scores) / len(scores), 4) if scores else None


def _calibration_data(records, prob_key, hit_key):
    """Dados para reliability diagram: prob prevista vs WR real por banda.
    prob_key armazena probabilidade em escala 0-100.
    Bandas: 0-20%, 20-40%, 40-60%, 60-80%, 80-100%.
    """
    bands = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]
    result = []
    for lo, hi in bands:
        subset = []
        for r in records:
            prob = r.get(prob_key)
            hit  = r.get(hit_key)
            if prob is not None and hit is not None:
                try:
                    if lo <= float(prob) < hi:
                        subset.append(r)
                except (ValueError, TypeError):
                    pass
        hits = sum(1 for r in subset if r.get(hit_key))
        mid  = round((lo + hi) / 2 / 100, 2)  # converter para 0-1 para display
        result.append({
            "band":      f"{lo}%–{hi}%",
            "predicted": mid,
            "actual":    round(hits / len(subset), 3) if subset else None,
            "n":         len(subset),
        })
    return result


def _est_odds(t):
    stored = t.get("combined_odds")
    if stored:
        return stored
    combined = 1.0
    for p in t.get("picks", []):
        prob = p.get("prob", 0)
        if prob and prob > 0.05:
            combined *= 1.0 / prob
    return round(combined, 2) if combined > 1.01 else None


def _treble_profit(t):
    if t.get("hit") is True:
        profit = t.get("profit_1u")
        if profit is None:
            odds = _est_odds(t)
            profit = (odds - 1) if odds else 0.0
    else:
        p = t.get("profit_1u")
        profit = p if p is not None else -1.0
    return profit


def analyze_football(history, trebles):
    records = history.get("records", [])

    if not records:
        return {
            "total": 0,
            "dates_processed": 0,
            "per_market": {},
            "by_confidence": {},
            "by_league": {},
            "trebles": {"total": 0, "won": 0, "win_rate": 0.0, "roi": 0.0, "roi_pct": 0.0, "avg_odds": 0.0, "pending": 0},
            "recent_7d": {"records": 0, "per_market": {}},
            "daily": {},
            "cum_o25_series": [],
            "cum_btts_series": [],
            "cum_treble_series": [],
            "brier_scores": {},
            "calibration": {},
        }

    # hit_xg não existe no schema actual — o resultado de xG está em hit_goal_range
    markets = [("1x2", "pick_1x2", "hit_1x2"), ("o25", "pick_o25", "hit_o25"),
               ("btts", "pick_btts", "hit_btts"), ("xg", "pick_xg", "hit_goal_range")]
    per_market = {m: segment_stats(records, pk, hk) for m, pk, hk in markets}

    # Brier Scores — campos reais: po (prob over, 0-100), pb (prob btts, 0-100)
    brier_scores = {
        "o25":  _brier_score(records, "po", "hit_o25"),
        "btts": _brier_score(records, "pb", "hit_btts"),
    }

    # Reliability diagram data
    calibration = {
        "o25":  _calibration_data(records, "po", "hit_o25"),
        "btts": _calibration_data(records, "pb", "hit_btts"),
    }

    # Por nível de confiança
    by_confidence = {}
    for conf in ["ALTA", "MÉDIA", "BAIXA"]:
        subset = [r for r in records if r.get("conf") == conf]
        combos = [("pick_1x2", "hit_1x2"), ("pick_o25", "hit_o25"), ("pick_btts", "hit_btts")]
        all_picks = sum(1 for r in subset for pk, hk in combos if r.get(pk) and r.get(hk) is not None)
        all_wins  = sum(1 for r in subset for pk, hk in combos if r.get(pk) and r.get(hk))
        ci_low, ci_high = wilson_ci(all_wins, all_picks)
        by_confidence[conf] = {
            "records":  len(subset),
            "picks":    all_picks,
            "wins":     all_wins,
            "win_rate": all_wins / all_picks if all_picks else 0.0,
            "ci_low":   ci_low,
            "ci_high":  ci_high,
            "reliable": all_picks >= 20,
        }

    # Por liga (top 12 por volume de registos)
    leagues: dict = {}
    for r in records:
        lg = r.get("league") or "Desconhecida"
        leagues.setdefault(lg, []).append(r)

    by_league = {}
    for lg, recs in sorted(leagues.items(), key=lambda x: len(x[1]), reverse=True)[:12]:
        o25 = segment_stats(recs, "pick_o25", "hit_o25")
        bts = segment_stats(recs, "pick_btts", "hit_btts")
        by_league[lg] = {
            "records":       len(recs),
            "o25_picks":     o25["picks"],  "o25_wr":   o25["win_rate"],
            "btts_picks":    bts["picks"],  "btts_wr":  bts["win_rate"],
            "o25_reliable":  o25["reliable"],
            "btts_reliable": bts["reliable"],
        }

    # Trebles
    t_hist     = trebles.get("history", [])
    t_resolved = [t for t in t_hist if t.get("hit") is not None]
    t_won      = [t for t in t_resolved if t.get("hit") is True]
    treble_roi = 0.0
    cum_treble, cum_treble_series = 0.0, []
    for t in t_resolved:
        profit = _treble_profit(t)
        treble_roi += profit
        cum_treble += profit
        cum_treble_series.append(round(cum_treble, 2))

    est_odds_list = [o for o in (_est_odds(t) for t in t_resolved) if o]
    n_tr, k_tr = len(t_resolved), len(t_won)
    ci_tr_l, ci_tr_h = wilson_ci(k_tr, n_tr)
    treble_stats = {
        "total":          n_tr,
        "won":            k_tr,
        "win_rate":       k_tr / n_tr if n_tr else 0.0,
        "ci_low":         ci_tr_l,
        "ci_high":        ci_tr_h,
        "reliable":       n_tr >= 10,
        "roi":            treble_roi,
        "roi_pct":        (treble_roi / n_tr * 100) if n_tr else 0.0,
        "avg_odds":       sum(est_odds_list) / len(est_odds_list) if est_odds_list else 0.0,
        "odds_estimated": not any(t.get("combined_odds") for t in t_resolved),
        "pending":        len(trebles.get("pending", [])),
    }

    # Últimos 7 dias
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    dates_processed = history.get("dates_processed", [])
    _min_aware = datetime.min.replace(tzinfo=timezone.utc)
    recent_dates = {d[:10] for d in dates_processed if (parse_date(d) or _min_aware) >= cutoff}
    recent_records = [r for r in records if r.get("date", "")[:10] in recent_dates]
    recent_pm = {m: segment_stats(recent_records, pk, hk) for m, pk, hk in markets}

    # Stats diárias
    daily: dict = {}
    for r in records:
        d = (r.get("date") or "")[:10]
        if not d:
            continue
        daily.setdefault(d, {"records": 0, "o25_picks": 0, "o25_wins": 0, "btts_picks": 0, "btts_wins": 0})
        daily[d]["records"] += 1
        if r.get("pick_o25") and r.get("hit_o25") is not None:
            daily[d]["o25_picks"] += 1
            if r.get("hit_o25"):
                daily[d]["o25_wins"] += 1
        if r.get("pick_btts") and r.get("hit_btts") is not None:
            daily[d]["btts_picks"] += 1
            if r.get("hit_btts"):
                daily[d]["btts_wins"] += 1
    daily = dict(sorted(daily.items()))

    # Séries ROI acumulado para gráficos — apenas picks resolvidos
    cum_o25, cum_btts = 0.0, 0.0
    cum_o25_series, cum_btts_series = [], []
    for r in records:
        if r.get("pick_o25") and r.get("hit_o25") is not None:
            cum_o25 += 1 if r.get("hit_o25") else -1
            cum_o25_series.append(round(cum_o25, 2))
        if r.get("pick_btts") and r.get("hit_btts") is not None:
            cum_btts += 1 if r.get("hit_btts") else -1
            cum_btts_series.append(round(cum_btts, 2))

    return {
        "total":            len(records),
        "dates_processed":  len(dates_processed),
        "per_market":       per_market,
        "by_confidence":    by_confidence,
        "by_league":        by_league,
        "trebles":          treble_stats,
        "recent_7d":        {"records": len(recent_records), "per_market": recent_pm},
        "daily":            daily,
        "cum_o25_series":   cum_o25_series,
        "cum_btts_series":  cum_btts_series,
        "cum_treble_series": cum_treble_series,
        "brier_scores":     brier_scores,
        "calibration":      calibration,
    }
