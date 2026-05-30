# picks_tracker.py — Backtest próprio do Analista: regista picks do dia e resolve resultados
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join("docs", "picks_today_db.json")


def load_db():
    if not os.path.exists(DB_PATH):
        return {"pending": [], "resolved": []}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"pending": [], "resolved": []}


def save_db(db):
    os.makedirs("docs", exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _norm(s):
    return (s or "").strip().lower()


def _match(pick, rec):
    return (rec.get("date", "")[:10] == pick["date"]
            and _norm(rec.get("home", "")) == _norm(pick["home"])
            and _norm(rec.get("away", "")) == _norm(pick["away"]))


def _get_hit(rec, market):
    key = {"o25": "hit_o25", "btts": "hit_btts", "1x2": "hit_1x2"}.get(market)
    if not key:
        return None
    val = rec.get(key)
    return None if val is None else bool(val)


def record_and_resolve(today_games, history_records):
    """
    Resolve picks pendentes contra history_records, depois regista as picks de hoje.
    Devolve o DB actualizado.
    """
    db        = load_db()
    now_iso   = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Resolver picks pendentes
    still_pending, newly_resolved = [], []
    for pick in db["pending"]:
        resolved = False
        for rec in history_records:
            if _match(pick, rec):
                hit = _get_hit(rec, pick["market"])
                if hit is not None:
                    newly_resolved.append({**pick, "hit": hit, "resolved_at": now_iso})
                    resolved = True
                    break
        if not resolved:
            still_pending.append(pick)

    db["pending"]  = still_pending
    db["resolved"].extend(newly_resolved)
    if newly_resolved:
        print(f"[tracker] {len(newly_resolved)} picks resolvidos")

    # 2. Registar picks de hoje (dedup por data+equipas+mercado)
    existing = {
        (p["date"], _norm(p["home"]), _norm(p["away"]), p["market"])
        for p in db["pending"] + db["resolved"]
    }
    added = 0
    for game in today_games:
        for pick in game.get("picks", []):
            key = (today_str, _norm(game["home"]), _norm(game["away"]), pick["market"])
            if key not in existing:
                db["pending"].append({
                    "date":      today_str,
                    "home":      game["home"],
                    "away":      game["away"],
                    "league":    game["league"],
                    "conf":      game["conf"],
                    "market":    pick["market"],
                    "edge":      pick["edge"],
                    "odds":      pick["odds"],
                    "kelly_pct": pick["kelly_pct"],
                })
                existing.add(key)
                added += 1

    if added:
        print(f"[tracker] {added} novas picks registadas para {today_str}")

    save_db(db)
    return db


def tracker_stats(db):
    """Calcula estatísticas de performance do backtest próprio do Analista."""
    resolved = db.get("resolved", [])
    pending  = db.get("pending",  [])

    if not resolved:
        return {
            "total_resolved": 0, "total_pending": len(pending),
            "wins": 0, "losses": 0, "win_rate": 0.0,
            "roi": 0.0, "roi_pct": 0.0,
            "by_edge": {}, "by_market": {}, "series": [], "recent": [],
        }

    def _seg(subset):
        if not subset:
            return None
        k = sum(1 for p in subset if p.get("hit"))
        s = len(subset)
        r = sum((p["odds"] - 1) if p.get("hit") else -1.0 for p in subset)
        return {"n": s, "wins": k, "win_rate": k / s, "roi": round(r, 2)}

    wins = sum(1 for p in resolved if p.get("hit"))
    n    = len(resolved)
    roi  = sum((p["odds"] - 1) if p.get("hit") else -1.0 for p in resolved)

    by_edge = {}
    for edge in ("strong", "moderate", "weak", "insufficient"):
        seg = _seg([p for p in resolved if p.get("edge") == edge])
        if seg:
            by_edge[edge] = seg

    by_market = {}
    for mkt in ("o25", "btts", "1x2"):
        seg = _seg([p for p in resolved if p.get("market") == mkt])
        if seg:
            by_market[mkt] = seg

    # Série ROI acumulado (ordenada por resolved_at)
    sorted_r = sorted(resolved, key=lambda p: p.get("resolved_at", ""))
    cum, series = 0.0, []
    for p in sorted_r:
        cum += (p["odds"] - 1) if p.get("hit") else -1.0
        series.append({
            "label":  f"{p['home'][:14]} vs {p['away'][:14]}",
            "market": p["market"].upper(),
            "hit":    p.get("hit"),
            "date":   p.get("date", ""),
            "cum":    round(cum, 2),
        })

    return {
        "total_resolved": n,
        "total_pending":  len(pending),
        "wins":      wins,
        "losses":    n - wins,
        "win_rate":  wins / n,
        "roi":       round(roi, 2),
        "roi_pct":   round(roi / n * 100, 1),
        "by_edge":   by_edge,
        "by_market": by_market,
        "series":    series,
        "recent":    list(reversed(sorted_r[-20:])),
    }
