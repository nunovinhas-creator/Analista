# analyze_over25.py — Métricas e análise do over25-scanner
# Nota: todos os campos numéricos chegam como strings do JSON do scanner
from datetime import datetime, timezone, timedelta
from utils import wilson_ci, parse_date, kelly_quarter, safe_float


def _safe_odds(p):
    v = safe_float(p.get("odds_over"))
    return v if 1.01 <= v <= 50.0 else None


def _max_drawdown(cum_series):
    """Drawdown máximo a partir da série de ROI acumulado."""
    if not cum_series:
        return 0.0
    peak, max_dd = cum_series[0], 0.0
    for v in cum_series:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def _roi_for_list(picks):
    roi, count = 0.0, 0
    for p in picks:
        if p.get("result_over25") not in ("WIN", "LOSS"):
            continue
        odds = _safe_odds(p)
        if odds is None:
            continue
        count += 1
        roi += (odds - 1) if p["result_over25"] == "WIN" else -1
    return roi, count


def _segment(subset):
    resolved = [p for p in subset if p.get("result_over25") in ("WIN", "LOSS")]
    wins = sum(1 for p in resolved if p["result_over25"] == "WIN")
    roi, cnt = _roi_for_list(resolved)
    n, k = len(resolved), wins
    ci_low, ci_high = wilson_ci(k, n)
    return {
        "count":    n,
        "wins":     k,
        "win_rate": k / n if n else 0.0,
        "ci_low":   ci_low,
        "ci_high":  ci_high,
        "reliable": n >= 20,
        "roi":      roi,
        "roi_pct":  (roi / cnt * 100) if cnt else 0.0,
    }


def analyze_over25(picks, picks_1x2):
    resolved = [p for p in picks if p.get("result_over25") in ("WIN", "LOSS")]
    wins = sum(1 for p in resolved if p["result_over25"] == "WIN")
    total_roi, bet_count = _roi_for_list(resolved)

    n, k = len(resolved), wins
    wr = k / n if n else 0.0
    ci_low, ci_high = wilson_ci(k, n)
    _min = datetime.min.replace(tzinfo=timezone.utc)

    # Série de vitórias/derrotas actual — sorted by date for correctness
    streak, streak_type = 0, None
    for p in reversed(sorted(resolved, key=lambda x: parse_date(x.get("data")) or _min)):
        r = p["result_over25"]
        if streak_type is None:
            streak_type = r
        if r == streak_type:
            streak += 1
        else:
            break

    # CLV médio (campo vem como string; "" = sem dados)
    clv_vals = []
    for p in picks:
        raw = p.get("clv")
        if raw is None or raw == "":
            continue
        try:
            clv_vals.append(float(raw))
        except (ValueError, TypeError):
            pass
    avg_clv = sum(clv_vals) / len(clv_vals) if clv_vals else None

    # Últimos 7 dias
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = [p for p in resolved if (parse_date(p.get("data")) or _min) >= cutoff]
    roi_recent, cnt_recent = _roi_for_list(recent)
    wins_recent = sum(1 for p in recent if p["result_over25"] == "WIN")

    # Por movimento de odds
    by_movement = {
        "SHORTENING": _segment([p for p in picks if p.get("movimento") == "SHORTENING"]),
        "DRIFTING":   _segment([p for p in picks if p.get("movimento") == "DRIFTING"]),
    }

    # Por score do sistema
    by_score = {}
    for lo, hi, label in [(0, 40, "0–40"), (40, 60, "40–60"), (60, 75, "60–75"), (75, 101, "75–100")]:
        by_score[label] = _segment([p for p in picks if lo <= safe_float(p.get("score_sistema")) < hi])

    # Por xG total
    by_xg = {}
    for lo, hi, label in [(0, 2.0, "< 2.0"), (2.0, 2.5, "2.0–2.5"), (2.5, 3.0, "2.5–3.0"), (3.0, 99, "≥ 3.0")]:
        by_xg[label] = _segment([p for p in picks if lo <= safe_float(p.get("xg_total")) < hi])

    # Por banda de odds
    by_odds = {}
    for lo, hi, label in [(1.0, 1.60, "< 1.60"), (1.60, 1.80, "1.60–1.80"), (1.80, 2.00, "1.80–2.00"), (2.00, 50.0, "≥ 2.00")]:
        subset = [p for p in picks if (o := _safe_odds(p)) is not None and lo <= o < hi]
        by_odds[label] = _segment(subset)

    # Por liga (top 12 por volume)
    leagues: dict = {}
    for p in picks:
        lg = p.get("liga") or "Desconhecida"
        leagues.setdefault(lg, []).append(p)
    by_league = {
        lg: _segment(v)
        for lg, v in sorted(leagues.items(), key=lambda x: len(x[1]), reverse=True)[:12]
        if len(v) >= 3
    }

    # Stats diárias
    daily: dict = {}
    for p in resolved:
        d = parse_date(p.get("data"))
        if not d:
            continue
        day = d.strftime("%Y-%m-%d")
        daily.setdefault(day, {"picks": 0, "wins": 0, "roi": 0.0})
        daily[day]["picks"] += 1
        if p["result_over25"] == "WIN":
            daily[day]["wins"] += 1
        odds = _safe_odds(p)
        if odds:
            daily[day]["roi"] += (odds - 1) if p["result_over25"] == "WIN" else -1
    daily = dict(sorted(daily.items()))

    # Série ROI acumulado + Rolling WR — apenas picks com odds válidas
    cumulative_roi: list = []
    rolling_wr_series = []
    cum = 0.0
    window = 20
    sorted_resolved = sorted(resolved, key=lambda x: parse_date(x.get("data")) or _min)
    bet_results: list = []
    for p in sorted_resolved:
        odds = _safe_odds(p)
        if odds is None:
            continue
        is_win = p["result_over25"] == "WIN"
        cum += (odds - 1) if is_win else -1
        cumulative_roi.append(round(cum, 3))
        bet_results.append(1 if is_win else 0)
        start = max(0, len(bet_results) - window)
        sub = bet_results[start:]
        rolling_wr_series.append(round(sum(sub) / len(sub), 3))

    # Drawdown máximo
    max_drawdown = _max_drawdown(cumulative_roi)

    # Análise 1X2 sharp
    p1x2_resolved = [p for p in picks_1x2 if p.get("resultado_outcome") in ("WIN", "LOSS")] if picks_1x2 else []
    wins_1x2 = sum(1 for p in p1x2_resolved if p["resultado_outcome"] == "WIN")
    roi_1x2, cnt_1x2 = 0.0, 0
    for p in p1x2_resolved:
        odds = safe_float(p.get("odds_entrada"))
        if 1.01 <= odds <= 50.0:
            cnt_1x2 += 1
            roi_1x2 += (odds - 1) if p["resultado_outcome"] == "WIN" else -1
    n_1x2, k_1x2 = len(p1x2_resolved), wins_1x2
    ci_1x2_l, ci_1x2_h = wilson_ci(k_1x2, n_1x2)

    # Picks pendentes com Kelly recomendado
    pending_with_kelly = []
    for p in picks:
        if p.get("result_over25") in ("WIN", "LOSS"):
            continue
        odds = _safe_odds(p)
        if n >= 10:
            kq = kelly_quarter(wr, odds or 0.0, cap=3.0)
            if avg_clv is not None and avg_clv < 0 and kq > 0:
                kq = round(kq * 0.5, 1)
            note = "CLV negativo: stake reduzido 50%" if (avg_clv is not None and avg_clv < 0) else ""
        else:
            kq = 0.0
            note = "n<10 resolvidos — sem recomendação"
        pending_with_kelly.append({
            "casa":      p.get("casa") or "—",
            "fora":      p.get("fora") or "—",
            "liga":      p.get("liga") or "—",
            "odds":      odds or 0.0,
            "score":     safe_float(p.get("score_sistema")),
            "movimento": p.get("movimento") or "—",
            "xg":        safe_float(p.get("xg_total")),

            "kelly_pct": kq,
            "kelly_ok":  kq >= 0.5,
            "kelly_note": note,
        })

    return {
        "total":       len(picks),
        "resolved":    n,
        "pending":     len(picks) - n,
        "wins":        k,
        "losses":      n - k,
        "win_rate":    wr,
        "ci_low":      ci_low,
        "ci_high":     ci_high,
        "roi":         total_roi,
        "roi_pct":     (total_roi / bet_count * 100) if bet_count else 0.0,
        "bet_count":   bet_count,
        "streak":      streak,
        "streak_type": streak_type or "",
        "avg_clv":     avg_clv,
        "max_drawdown": max_drawdown,
        "recent_7d": {
            "count":    len(recent),
            "wins":     wins_recent,
            "win_rate": wins_recent / len(recent) if recent else 0.0,
            "roi":      roi_recent,
            "roi_pct":  (roi_recent / cnt_recent * 100) if cnt_recent else 0.0,
        },
        "by_movement": by_movement,
        "by_score":    by_score,
        "by_xg":       by_xg,
        "by_odds":     by_odds,
        "by_league":   by_league,
        "daily":       daily,
        "cumulative_roi":    cumulative_roi,
        "rolling_wr_series": rolling_wr_series,
        "picks_1x2": {
            "resolved": n_1x2,
            "wins":     k_1x2,
            "win_rate": k_1x2 / n_1x2 if n_1x2 else 0.0,
            "ci_low":   ci_1x2_l,
            "ci_high":  ci_1x2_h,
            "reliable": n_1x2 >= 20,
            "roi":      roi_1x2,
            "roi_pct":  (roi_1x2 / cnt_1x2 * 100) if cnt_1x2 else 0.0,
        },
        "all_picks_raw": sorted(picks, key=lambda x: parse_date(x.get("data")) or _min, reverse=True)[:30],
        "pending_picks": sorted(
            [p for p in picks if p.get("result_over25") not in ("WIN", "LOSS")],
            key=lambda x: parse_date(x.get("data")) or _min,
            reverse=True,
        ),
        "pending_with_kelly": pending_with_kelly,
    }
