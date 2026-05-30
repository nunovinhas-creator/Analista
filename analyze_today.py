# analyze_today.py — "Onde Apostar Hoje": picks do dia qualificados pelo backtest
import re
from datetime import datetime, timezone

MARKET_BASE_ODDS = {"o25": 1.90, "btts": 1.85, "1x2": 2.20}
MARKET_LABELS    = {"o25": "Over 2.5", "btts": "BTTS", "1x2": "1X2"}
CONF_RANK        = {"ALTA": 0, "MÉDIA": 1, "BAIXA": 2}
MIN_N_EDGE       = 10   # mínimo para sinalizar edge (strong/moderate)
MIN_N_SHOW       = 5    # mínimo para mostrar qualquer stat


def _wilson_ci(wins, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z * (p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def _seg(records, pick_key, hit_key):
    bets = [r for r in records if r.get(pick_key) and r.get(hit_key) is not None]
    wins = sum(1 for r in bets if r.get(hit_key))
    n, k = len(bets), wins
    ci_l, ci_h = _wilson_ci(k, n)
    return {
        "n": n, "wins": k,
        "win_rate": k / n if n else 0.0,
        "ci_low":   ci_l,
        "ci_high":  ci_h,
        "reliable": n >= 20,
        "roi":      k - (n - k),
    }


def _kelly_q(wr, odds, cap=3.0):
    if odds <= 1.01 or wr <= 0:
        return 0.0
    b = odds - 1
    return round(min(max((wr * b - (1 - wr)) / b / 4, 0.0) * 100, cap), 1)


def parse_dashboard_html(html, today_str):
    """Extrai picks do football-dashboard HTML para o dia indicado."""
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

        tip_m = re.search(r'class="tip-badge">([^<]+)<', block)
        tip   = tip_m.group(1).strip() if tip_m else ""

        # Extra pills: hot-green = O2.5 ou BTTS activo como pick
        pick_o25  = "Over 2.5 Golos" in tip
        pick_btts = False
        for pill_cls, pill_html in re.findall(r'class="extra-pill([^"]*)">(.*?)</div>', block, re.DOTALL):
            if "hot-green" not in pill_cls:
                continue
            pill_text = re.sub(r"<[^>]+>", "", pill_html).strip()
            if "Over 2.5" in pill_text:
                pick_o25 = True
            if "BTTS" in pill_text:
                pick_btts = True

        pick_1x2 = any(x in tip for x in ("Vitória Casa", "Vitória Fora", "Empate provável"))
        pick_dir  = ("H" if "Vitória Casa" in tip
                     else ("A" if "Vitória Fora" in tip
                           else ("D" if "Empate" in tip else None)))

        if not (pick_o25 or pick_btts or pick_1x2):
            continue

        def _f(key):
            try:
                return float(attrs.get(key, 0))
            except (ValueError, TypeError):
                return 0.0

        games.append({
            "home":       home_m.group(1).strip(),
            "away":       away_m.group(1).strip(),
            "league":     attrs.get("league", "Desconhecida"),
            "ko_hour":    attrs.get("hour", ""),
            "conf":       attrs.get("conf", "BAIXA"),
            "tip":        tip,
            "pick_o25":   pick_o25,
            "pick_btts":  pick_btts,
            "pick_1x2":   pick_1x2,
            "pick_dir":   pick_dir,
            "prob_o25":   _f("o25"),
            "prob_btts":  _f("btts"),
            "prob_hw":    _f("hw"),
            "prob_dr":    _f("dr"),
            "prob_aw":    _f("aw"),
            "xg_total":   _f("xgtotal"),
        })

    return games


def analyze_today(history, dashboard_html):
    """Cruza picks do dia com estatísticas do backtest e devolve recomendações."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    records   = history.get("records", [])

    markets = [
        ("o25",  "pick_o25",  "hit_o25"),
        ("btts", "pick_btts", "hit_btts"),
        ("1x2",  "pick_1x2",  "hit_1x2"),
    ]

    # --- Backtest: estatísticas do corpus resolvido ---
    global_stats = {mk: _seg(records, pk, hk) for mk, pk, hk in markets}

    conf_stats = {}
    for conf in ("ALTA", "MÉDIA", "BAIXA"):
        subset = [r for r in records if r.get("conf") == conf]
        conf_stats[conf] = {mk: _seg(subset, pk, hk) for mk, pk, hk in markets}

    league_map: dict = {}
    for r in records:
        lg = r.get("league") or "Desconhecida"
        league_map.setdefault(lg, []).append(r)
    league_stats = {
        lg: {mk: _seg(recs, pk, hk) for mk, pk, hk in markets}
        for lg, recs in league_map.items()
    }

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

            # Estatística de referência: conf-específica se tiver n suficiente
            if cs.get("n", 0) >= MIN_N_SHOW:
                ref       = cs
                ref_label = f"{conf}"
            else:
                ref       = gs
                ref_label = "global"

            ref_wr    = ref.get("win_rate", 0)
            ref_n     = ref.get("n", 0)
            ref_ci_l  = ref.get("ci_low", 0)
            ref_ci_h  = ref.get("ci_high", 1)

            kq = _kelly_q(ref_wr, odds)

            # Sinal de edge
            break_even = 1.0 / odds
            if ref_n >= MIN_N_EDGE and ref_ci_l > break_even:
                edge = "strong"      # CI inferior acima do break-even
            elif ref_n >= MIN_N_SHOW and ref_wr > break_even:
                edge = "moderate"    # EV positivo mas CI ainda largo
            elif ref_n >= MIN_N_SHOW:
                edge = "weak"        # EV negativo
            else:
                edge = "insufficient"  # dados insuficientes

            scored.append({
                "market":    mk,
                "label":     label,
                "odds":      odds,
                # referência usada para Kelly e sinal
                "ref_label": ref_label,
                "ref_wr":    ref_wr,
                "ref_n":     ref_n,
                "ref_ci_l":  ref_ci_l,
                "ref_ci_h":  ref_ci_h,
                "ref_reliable": ref.get("reliable", False),
                # backtest global (contexto)
                "global_wr": gs.get("win_rate", 0),
                "global_n":  gs.get("n", 0),
                # backtest liga (contexto adicional)
                "league_wr": ls.get("win_rate", 0),
                "league_n":  ls.get("n", 0),
                "league_ci_l": ls.get("ci_low", 0),
                "league_ci_h": ls.get("ci_high", 1),
                # Kelly e edge
                "kelly_pct": kq,
                "edge":      edge,
                # direcção 1X2 se aplicável
                "dir":       g.get("pick_dir") if mk == "1x2" else None,
            })

        if not scored:
            continue

        n_strong   = sum(1 for p in scored if p["edge"] == "strong")
        n_moderate = sum(1 for p in scored if p["edge"] == "moderate")

        games_out.append({
            "home":      g["home"],
            "away":      g["away"],
            "league":    league,
            "ko_hour":   g["ko_hour"],
            "conf":      conf,
            "conf_rank": CONF_RANK.get(conf, 2),
            "tip":       g["tip"],
            "picks":     scored,
            "prob_o25":  g["prob_o25"],
            "prob_btts": g["prob_btts"],
            "prob_hw":   g["prob_hw"],
            "prob_dr":   g["prob_dr"],
            "prob_aw":   g["prob_aw"],
            "xg_total":  g["xg_total"],
            "n_strong":  n_strong,
            "n_moderate": n_moderate,
        })

    games_out.sort(key=lambda g: (g["conf_rank"], -g["n_strong"], -g["n_moderate"]))

    return {
        "today":        today_str,
        "total_games":  len(games_out),
        "total_picks":  sum(len(g["picks"]) for g in games_out),
        "strong_picks": sum(g["n_strong"] for g in games_out),
        "global_stats": global_stats,
        "conf_stats":   conf_stats,
        "backtest_n":   len(records),
        "games":        games_out,
    }
