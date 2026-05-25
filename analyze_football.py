# analyze_football.py — Métricas e análise do football-dashboard (Matemática Da Bola)
from datetime import datetime, timezone, timedelta


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _market_segment(records, pick_key, hit_key):
    picks = [r for r in records if r.get(pick_key)]
    wins  = [r for r in picks  if r.get(hit_key)]
    roi   = len(wins) - (len(picks) - len(wins))  # odds 2.0 implícitas (flat)
    return {
        "picks":    len(picks),
        "wins":     len(wins),
        "win_rate": len(wins) / len(picks) if picks else 0.0,
        "roi":      roi,
        "roi_pct":  (roi / len(picks) * 100) if picks else 0.0,
    }


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
        }

    # Por mercado
    markets = [("1x2", "pick_1x2", "hit_1x2"), ("o25", "pick_o25", "hit_o25"),
               ("btts", "pick_btts", "hit_btts"), ("xg", "pick_xg", "hit_xg")]
    per_market = {m: _market_segment(records, pk, hk) for m, pk, hk in markets}

    # Por nível de confiança
    by_confidence = {}
    for conf in ["ALTA", "MÉDIA", "BAIXA"]:
        subset = [r for r in records if r.get("confidence") == conf]
        all_picks = sum(1 for r in subset for pk, hk in [("pick_1x2","hit_1x2"),("pick_o25","hit_o25"),("pick_btts","hit_btts")] if r.get(pk))
        all_wins  = sum(1 for r in subset for pk, hk in [("pick_1x2","hit_1x2"),("pick_o25","hit_o25"),("pick_btts","hit_btts")] if r.get(pk) and r.get(hk))
        by_confidence[conf] = {
            "records": len(subset),
            "picks":   all_picks,
            "wins":    all_wins,
            "win_rate": all_wins / all_picks if all_picks else 0.0,
        }

    # Por liga (top 12 por volume de registos)
    leagues: dict = {}
    for r in records:
        lg = r.get("league") or "Desconhecida"
        leagues.setdefault(lg, []).append(r)

    by_league = {}
    for lg, recs in sorted(leagues.items(), key=lambda x: len(x[1]), reverse=True)[:12]:
        o25 = _market_segment(recs, "pick_o25", "hit_o25")
        bts = _market_segment(recs, "pick_btts", "hit_btts")
        by_league[lg] = {
            "records":   len(recs),
            "o25_picks": o25["picks"], "o25_wr": o25["win_rate"],
            "btts_picks": bts["picks"], "btts_wr": bts["win_rate"],
        }

    # Trebles
    t_hist = trebles.get("history", [])
    t_won = [t for t in t_hist if t.get("hit") is True]
    treble_roi = sum(t.get("profit_1u", t.get("combined_odds", 1) - 1) for t in t_won) - (len(t_hist) - len(t_won))
    treble_stats = {
        "total":    len(t_hist),
        "won":      len(t_won),
        "win_rate": len(t_won) / len(t_hist) if t_hist else 0.0,
        "roi":      treble_roi,
        "roi_pct":  (treble_roi / len(t_hist) * 100) if t_hist else 0.0,
        "avg_odds": sum(t.get("combined_odds", 0) for t in t_hist) / len(t_hist) if t_hist else 0.0,
        "pending":  len(trebles.get("pending", [])),
    }

    # Últimos 7 dias
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    dates_processed = history.get("dates_processed", [])
    recent_dates = {d for d in dates_processed if (_parse_date(d) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff}
    recent_records = [r for r in records if r.get("date", "")[:10] in recent_dates]
    recent_pm = {m: _market_segment(recent_records, pk, hk) for m, pk, hk in markets}

    # Stats diárias
    daily: dict = {}
    for r in records:
        d = (r.get("date") or "")[:10]
        if not d:
            continue
        daily.setdefault(d, {"records": 0, "o25_picks": 0, "o25_wins": 0, "btts_picks": 0, "btts_wins": 0})
        daily[d]["records"] += 1
        if r.get("pick_o25"):
            daily[d]["o25_picks"] += 1
            if r.get("hit_o25"):
                daily[d]["o25_wins"] += 1
        if r.get("pick_btts"):
            daily[d]["btts_picks"] += 1
            if r.get("hit_btts"):
                daily[d]["btts_wins"] += 1
    daily = dict(sorted(daily.items()))

    # Séries ROI acumulado para gráficos
    cum_o25, cum_btts = 0.0, 0.0
    cum_o25_series, cum_btts_series = [], []
    for r in records:
        if r.get("pick_o25"):
            cum_o25 += 1 if r.get("hit_o25") else -1
            cum_o25_series.append(round(cum_o25, 2))
        if r.get("pick_btts"):
            cum_btts += 1 if r.get("hit_btts") else -1
            cum_btts_series.append(round(cum_btts, 2))

    cum_treble, cum_treble_series = 0.0, []
    for t in t_hist:
        if t.get("hit"):
            cum_treble += t.get("profit_1u", t.get("combined_odds", 1) - 1)
        else:
            cum_treble -= 1
        cum_treble_series.append(round(cum_treble, 2))

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
    }
