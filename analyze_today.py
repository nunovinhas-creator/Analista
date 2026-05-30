# analyze_today.py — "Onde Apostar Hoje": picks do dia qualificados pelo backtest
import re
from datetime import datetime, timezone
from picks_tracker import record_and_resolve, tracker_stats

MARKET_BASE_ODDS = {"o25": 1.90, "btts": 1.85, "1x2": 2.20}
MARKET_LABELS    = {"o25": "Over 2.5", "btts": "BTTS", "1x2": "1X2"}
CONF_RANK        = {"ALTA": 0, "MÉDIA": 1, "BAIXA": 2}
MIN_N_REF        = 20   # mínimo para referência fiável (Wilson CI significativo)
MIN_N_SHOW       = 10   # mínimo para mostrar stat de contexto

# Limiares derivados da calibração do backtest do Matemática Da Bola (history.json, 257 registos)
# Regra: limiar mínimo = início da banda de probabilidade onde WR real > break-even
#
# Over 2.5 (odds 1.90x, break-even 52.6%):
#   banda 40-60%  → WR real 50.6%  → EV -2.1%  ❌  excluída
#   banda 60-80%  → WR real 55.2%  → EV +2.6%  ✅  limiar mínimo = 60%
PICK_THRESH_O25  = 60.0
#
# BTTS (odds 1.85x, break-even 54.1%):
#   banda 40-60%  → WR real 53.2%  → EV -0.8%  ❌  excluída
#   banda 60-80%  → WR real 63.5%  → EV +9.4%  ✅  limiar mínimo = 60%
PICK_THRESH_BTTS = 60.0
#
# 1X2 (odds 2.20x, break-even 45.5%), apenas ALTA/MÉDIA:
#   banda 55-65%  → WR real 53.8%  → EV +8.4%  ✅  limiar mínimo = 55%
PICK_THRESH_1X2  = 55.0

# Pesos de EV por mercado (derivados da calibração — usados no score composto)
_MKT_EV      = {"btts": 0.094, "1x2": 0.084, "o25": 0.026}
_EDGE_WEIGHT = {"strong": 2.0, "moderate": 1.0, "weak": 0.0, "insufficient": 0.0}
_EDGE_ORDER  = {"strong": 0, "moderate": 1, "weak": 2, "insufficient": 3}
_MKT_ORDER   = {"btts": 0, "1x2": 1, "o25": 2}


def _wilson_ci(wins, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z * (p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def _safe_float(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (ValueError, TypeError):
        return default


def _seg_mk(records, mk):
    """
    Segmenta registos por threshold de probabilidade real (campos po/pb/ph/pa),
    não pelo booleano do modelo. ROI calculado com odds reais do mercado.
    """
    odds   = MARKET_BASE_ODDS[mk]
    thresh = {"o25": PICK_THRESH_O25, "btts": PICK_THRESH_BTTS, "1x2": PICK_THRESH_1X2}[mk]

    if mk == "o25":
        bets = [r for r in records
                if _safe_float(r.get("po")) >= thresh and r.get("hit_o25") is not None]
        wins = sum(1 for r in bets if r["hit_o25"])
    elif mk == "btts":
        bets = [r for r in records
                if _safe_float(r.get("pb")) >= thresh and r.get("hit_btts") is not None]
        wins = sum(1 for r in bets if r["hit_btts"])
    else:  # 1x2
        bets = [r for r in records
                if max(_safe_float(r.get("ph")), _safe_float(r.get("pa"))) >= thresh
                and r.get("hit_1x2") is not None]
        wins = sum(1 for r in bets if r["hit_1x2"])

    n, k  = len(bets), wins
    ci_l, ci_h = _wilson_ci(k, n)
    roi = round(k * (odds - 1) - (n - k), 2)
    return {
        "n": n, "wins": k,
        "win_rate": k / n if n else 0.0,
        "ci_low":   ci_l,
        "ci_high":  ci_h,
        "reliable": n >= MIN_N_REF,
        "roi":      roi,
    }


def _kelly_q(wr, odds, cap=3.0):
    if odds <= 1.01 or wr <= 0:
        return 0.0
    b = odds - 1
    return round(min(max((wr * b - (1 - wr)) / b / 4, 0.0) * 100, cap), 1)


def parse_dashboard_html(html, today_str):
    """Extrai todos os jogos do dia do football-dashboard HTML."""
    games = []
    card_blocks = re.split(r'(?=<div class="card")', html)

    for block in card_blocks:
        if not block.strip().startswith('<div class="card"'):
            continue

        attrs = dict(re.findall(r'data-(\w+)="([^"]+)"', block))
        if attrs.get("date") != today_str:
            continue

        home_m = re.search(r'class="team home-team">([^<]+)<', block)
        away_m = re.search(r'class="team away-team">([^<]+)<', block)
        if not home_m or not away_m:
            continue

        def _f(key):
            try:
                return float(attrs.get(key, 0))
            except (ValueError, TypeError):
                return 0.0

        prob_o25  = _f("o25")
        prob_btts = _f("btts")
        prob_hw   = _f("hw")
        prob_aw   = _f("aw")
        conf_card = attrs.get("conf", "BAIXA")

        tip_m = re.search(r'class="tip-badge">([^<]+)<', block)
        tip   = tip_m.group(1).strip() if tip_m else ""

        # Picks por limiar de probabilidade — independente dos flags do football-dashboard
        pick_o25  = prob_o25  >= PICK_THRESH_O25
        pick_btts = prob_btts >= PICK_THRESH_BTTS

        # 1X2: apenas ALTA/MÉDIA, sem empate, direção do tip ou da probabilidade mais alta
        pick_dir = ("H" if "Vitória Casa" in tip
                    else ("A" if "Vitória Fora" in tip else None))
        best_dir  = "H" if prob_hw >= prob_aw else "A"
        best_prob = prob_hw if best_dir == "H" else prob_aw
        pick_1x2  = conf_card in ("ALTA", "MÉDIA") and best_prob >= PICK_THRESH_1X2
        if pick_1x2 and pick_dir is None:
            pick_dir = best_dir

        if not (pick_o25 or pick_btts or pick_1x2):
            continue

        games.append({
            "home":      home_m.group(1).strip(),
            "away":      away_m.group(1).strip(),
            "league":    attrs.get("league", "Desconhecida"),
            "ko_hour":   attrs.get("hour", ""),
            "conf":      conf_card,
            "tip":       tip,
            "pick_o25":  pick_o25,
            "pick_btts": pick_btts,
            "pick_1x2":  pick_1x2,
            "pick_dir":  pick_dir,
            "prob_o25":  prob_o25,
            "prob_btts": prob_btts,
            "prob_hw":   prob_hw,
            "prob_dr":   _f("dr"),
            "prob_aw":   prob_aw,
            "xg_total":  _f("xgtotal"),
        })

    return games


def analyze_today(history, dashboard_html):
    """Cruza picks do dia com estatísticas do backtest e devolve recomendações."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    records   = history.get("records", [])
    markets   = ["o25", "btts", "1x2"]

    # --- Backtest: stats threshold-based (campos reais po/pb/ph/pa, odds reais) ---
    global_stats = {mk: _seg_mk(records, mk) for mk in markets}

    conf_stats = {}
    for conf in ("ALTA", "MÉDIA", "BAIXA"):
        subset = [r for r in records if r.get("conf") == conf]
        conf_stats[conf] = {mk: _seg_mk(subset, mk) for mk in markets}

    league_map: dict = {}
    for r in records:
        league_map.setdefault(r.get("league") or "Desconhecida", []).append(r)
    league_stats = {lg: {mk: _seg_mk(recs, mk) for mk in markets}
                    for lg, recs in league_map.items()}

    # --- Picks de hoje ---
    today_games = parse_dashboard_html(dashboard_html, today_str) if dashboard_html else []
    print(f"[today] {len(today_games)} jogos com picks em {today_str}")

    # --- Qualificar cada pick ---
    pick_defs = [
        ("o25",  "pick_o25",  "Over 2.5"),
        ("btts", "pick_btts", "BTTS"),
        ("1x2",  "pick_1x2",  "1X2"),
    ]

    games_out = []
    for g in today_games:
        conf   = g["conf"]
        league = g["league"]
        scored = []

        for mk, pick_key, label in pick_defs:
            if not g.get(pick_key):
                continue

            odds = MARKET_BASE_ODDS[mk]
            gs   = global_stats[mk]
            cs   = conf_stats.get(conf, {}).get(mk, {})
            ls   = league_stats.get(league, {}).get(mk, {})

            # Hierarquia de referência: liga (n≥20) > conf (n≥20) > global
            if ls.get("n", 0) >= MIN_N_REF:
                ref, ref_label = ls, "liga"
            elif cs.get("n", 0) >= MIN_N_REF:
                ref, ref_label = cs, conf
            else:
                ref, ref_label = gs, "global"

            ref_wr   = ref.get("win_rate", 0)
            ref_n    = ref.get("n", 0)
            ref_ci_l = ref.get("ci_low", 0)
            ref_ci_h = ref.get("ci_high", 1)

            # Kelly apenas com referência fiável (n≥20)
            kq = _kelly_q(ref_wr, odds) if ref.get("reliable") else 0.0

            # Sinal de edge (mesmos limiares, agora com referência mais correcta)
            break_even = 1.0 / odds
            if ref_n >= MIN_N_REF and ref_ci_l > break_even:
                edge = "strong"
            elif ref_n >= MIN_N_REF and ref_wr > break_even:
                edge = "moderate"
            elif ref_n >= MIN_N_SHOW and ref_wr > break_even:
                edge = "moderate"   # EV positivo mas amostra ainda curta
            elif ref_n >= MIN_N_SHOW:
                edge = "weak"
            else:
                edge = "insufficient"

            scored.append({
                "market":       mk,
                "label":        label,
                "odds":         odds,
                "ref_label":    ref_label,
                "ref_wr":       ref_wr,
                "ref_n":        ref_n,
                "ref_ci_l":     ref_ci_l,
                "ref_ci_h":     ref_ci_h,
                "ref_reliable": ref.get("reliable", False),
                "global_wr":    gs.get("win_rate", 0),
                "global_n":     gs.get("n", 0),
                "league_wr":    ls.get("win_rate", 0),
                "league_n":     ls.get("n", 0),
                "league_ci_l":  ls.get("ci_low", 0),
                "league_ci_h":  ls.get("ci_high", 1),
                "kelly_pct":    kq,
                "edge":         edge,
                "dir":          g.get("pick_dir") if mk == "1x2" else None,
            })

        if not scored:
            continue

        n_strong   = sum(1 for p in scored if p["edge"] == "strong")
        n_moderate = sum(1 for p in scored if p["edge"] == "moderate")

        # Detecção de combinado BTTS+O2.5 (ambos com edge positivo)
        has_btts = any(p["market"] == "btts" and p["edge"] in ("strong", "moderate") for p in scored)
        has_o25  = any(p["market"] == "o25"  and p["edge"] in ("strong", "moderate") for p in scored)
        combined_btts_o25 = has_btts and has_o25
        combined_odds     = round(MARKET_BASE_ODDS["o25"] * MARKET_BASE_ODDS["btts"], 2) if combined_btts_o25 else None

        # Score composto: EV do mercado × peso do edge (ordena por valor esperado real)
        game_score = sum(_EDGE_WEIGHT.get(p["edge"], 0) * _MKT_EV.get(p["market"], 0)
                         for p in scored)

        games_out.append({
            "home":             g["home"],
            "away":             g["away"],
            "league":           league,
            "ko_hour":          g["ko_hour"],
            "conf":             conf,
            "conf_rank":        CONF_RANK.get(conf, 2),
            "tip":              g["tip"],
            "picks":            scored,
            "prob_o25":         g["prob_o25"],
            "prob_btts":        g["prob_btts"],
            "prob_hw":          g["prob_hw"],
            "prob_dr":          g["prob_dr"],
            "prob_aw":          g["prob_aw"],
            "xg_total":         g["xg_total"],
            "n_strong":         n_strong,
            "n_moderate":       n_moderate,
            "combined_btts_o25": combined_btts_o25,
            "combined_odds":    combined_odds,
            "game_score":       round(game_score, 4),
        })

    # Ordenar por score composto (EV real × evidência backtest), desempate por conf
    games_out.sort(key=lambda g: (-g["game_score"], g["conf_rank"]))

    # Top picks para o resumo do dia (apenas strong/moderate, ordenados por evidência)
    top_picks = []
    for g in games_out:
        for p in g["picks"]:
            if p["edge"] in ("strong", "moderate"):
                top_picks.append({
                    **p,
                    "home":    g["home"],
                    "away":    g["away"],
                    "league":  g["league"],
                    "ko_hour": g["ko_hour"],
                    "conf":    g["conf"],
                })
    top_picks.sort(key=lambda p: (
        _EDGE_ORDER.get(p["edge"], 3),
        _MKT_ORDER.get(p["market"], 3),
        -p.get("kelly_pct", 0),
    ))

    tracker_db = record_and_resolve(games_out, records)
    perf       = tracker_stats(tracker_db)

    return {
        "today":        today_str,
        "total_games":  len(games_out),
        "total_picks":  sum(len(g["picks"]) for g in games_out),
        "strong_picks": sum(g["n_strong"] for g in games_out),
        "global_stats": global_stats,
        "conf_stats":   conf_stats,
        "backtest_n":   len(records),
        "games":        games_out,
        "top_picks":    top_picks[:8],
        "tracker":      perf,
    }
