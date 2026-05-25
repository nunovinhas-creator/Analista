# analyze_over25.py — Métricas e análise do over25-scanner
# Nota: todos os campos numéricos chegam como strings do JSON do scanner
from datetime import datetime, timezone, timedelta


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _flt(p, key, default=0.0):
    """Converte campo string para float com fallback seguro."""
    v = p.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _safe_odds(p):
    v = _flt(p, "odds_over")
    return v if 1.01 <= v <= 50.0 else None


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
    return {
        "count": len(resolved),
        "wins": wins,
        "win_rate": wins / len(resolved) if resolved else 0.0,
        "roi": roi,
        "roi_pct": (roi / cnt * 100) if cnt else 0.0,
    }


def analyze_over25(picks, picks_1x2):
    resolved = [p for p in picks if p.get("result_over25") in ("WIN", "LOSS")]
    wins = sum(1 for p in resolved if p["result_over25"] == "WIN")
    total_roi, bet_count = _roi_for_list(resolved)

    # Série de vitórias/derrotas atual
    streak, streak_type = 0, None
    for p in reversed(resolved):
        r = p["result_over25"]
        if streak_type is None:
            streak_type = r
        if r == streak_type:
            streak += 1
        else:
            break

    # CLV médio (campo vem como string, "" significa sem dados)
    clv_vals = [_flt(p, "clv") for p in picks if p.get("clv") not in (None, "")]
    avg_clv = sum(clv_vals) / len(clv_vals) if clv_vals else None

    # Últimos 7 dias
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    _min = datetime.min.replace(tzinfo=timezone.utc)
    recent = [p for p in resolved if (_parse_date(p.get("data")) or _min) >= cutoff]
    roi_recent, cnt_recent = _roi_for_list(recent)
    wins_recent = sum(1 for p in recent if p["result_over25"] == "WIN")

    # Por movimento de odds
    by_movement = {
        "SHORTENING": _segment([p for p in picks if p.get("movimento") == "SHORTENING"]),
        "DRIFTING":   _segment([p for p in picks if p.get("movimento") == "DRIFTING"]),
    }

    # Por score do sistema (campo é string, ex: "58")
    by_score = {}
    for lo, hi, label in [(0, 40, "0–40"), (40, 60, "40–60"), (60, 75, "60–75"), (75, 101, "75–100")]:
        by_score[label] = _segment([p for p in picks if lo <= _flt(p, "score_sistema") < hi])

    # Por xG total (campo é string, ex: "4.19")
    by_xg = {}
    for lo, hi, label in [(0, 2.0, "< 2.0"), (2.0, 2.5, "2.0–2.5"), (2.5, 3.0, "2.5–3.0"), (3.0, 99, "≥ 3.0")]:
        by_xg[label] = _segment([p for p in picks if lo <= _flt(p, "xg_total") < hi])

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

    # Stats diárias para gráfico de barras
    daily: dict = {}
    for p in resolved:
        d = _parse_date(p.get("data"))
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

    # Série ROI acumulado para gráfico de linha
    cumulative_roi: list = []
    cum = 0.0
    sorted_resolved = sorted(resolved, key=lambda x: _parse_date(x.get("data")) or _min)
    for p in sorted_resolved:
        odds = _safe_odds(p)
        if odds:
            cum += (odds - 1) if p["result_over25"] == "WIN" else -1
        cumulative_roi.append(round(cum, 3))

    # Análise 1X2 sharp — campos reais: resultado_outcome, odds_entrada
    p1x2_resolved = [p for p in picks_1x2 if p.get("resultado_outcome") in ("WIN", "LOSS")] if picks_1x2 else []
    wins_1x2 = sum(1 for p in p1x2_resolved if p["resultado_outcome"] == "WIN")
    roi_1x2, cnt_1x2 = 0.0, 0
    for p in p1x2_resolved:
        odds = _flt(p, "odds_entrada")
        if 1.01 <= odds <= 50.0:
            cnt_1x2 += 1
            roi_1x2 += (odds - 1) if p["resultado_outcome"] == "WIN" else -1

    return {
        "total": len(picks),
        "resolved": len(resolved),
        "pending": len(picks) - len(resolved),
        "wins": wins,
        "losses": len(resolved) - wins,
        "win_rate": wins / len(resolved) if resolved else 0.0,
        "roi": total_roi,
        "roi_pct": (total_roi / bet_count * 100) if bet_count else 0.0,
        "bet_count": bet_count,
        "streak": streak,
        "streak_type": streak_type,
        "avg_clv": avg_clv,
        "recent_7d": {
            "count": len(recent),
            "wins": wins_recent,
            "win_rate": wins_recent / len(recent) if recent else 0.0,
            "roi": roi_recent,
            "roi_pct": (roi_recent / cnt_recent * 100) if cnt_recent else 0.0,
        },
        "by_movement": by_movement,
        "by_score":    by_score,
        "by_xg":       by_xg,
        "by_league":   by_league,
        "daily":       daily,
        "cumulative_roi": cumulative_roi,
        "picks_1x2": {
            "resolved": len(p1x2_resolved),
            "wins": wins_1x2,
            "win_rate": wins_1x2 / len(p1x2_resolved) if p1x2_resolved else 0.0,
            "roi": roi_1x2,
            "roi_pct": (roi_1x2 / cnt_1x2 * 100) if cnt_1x2 else 0.0,
        },
    }
