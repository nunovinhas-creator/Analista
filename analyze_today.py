# analyze_today.py — "Onde Apostar Hoje": picks do dia qualificados pelo backtest
import re
from datetime import timedelta
from picks_tracker import record_and_resolve, tracker_stats
from utils import wilson_ci, kelly_quarter, MARKET_BASE_ODDS, MARKET_LABELS, segment_stats, safe_float, now_lisbon

CONF_RANK        = {"ALTA": 0, "MÉDIA": 1, "BAIXA": 2}
MIN_N_EDGE       = 10   # mínimo para sinalizar edge (strong/moderate)
MIN_N_SHOW       = 5    # mínimo para mostrar qualquer stat

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


def _extract_1x2_dir(tip_text):
    if "Vitória Casa" in tip_text:
        return "H"
    if "Vitória Fora" in tip_text:
        return "A"
    return None


def _best_1x2(prob_hw, prob_aw):
    best_dir = "H" if prob_hw >= prob_aw else "A"
    return best_dir, (prob_hw if best_dir == "H" else prob_aw)


def _f(key, attrs):
    return safe_float(attrs.get(key, 0))


def parse_dashboard_html(html, dates):
    """Extrai jogos do football-dashboard HTML para as datas indicadas."""
    games = []
    card_blocks = re.split(r'(?=<div class="card")', html)

    for block in card_blocks:
        if not block.strip().startswith('<div class="card"'):
            continue

        attrs = dict(re.findall(r'data-(\w+)="([^"]+)"', block))
        if attrs.get("date") not in dates:
            continue

        home_m = re.search(r'class="team home-team">([^<]+)<', block)
        away_m = re.search(r'class="team away-team">([^<]+)<', block)
        if not home_m or not away_m:
            continue

        prob_o25  = _f("o25", attrs)
        prob_btts = _f("btts", attrs)
        prob_hw   = _f("hw", attrs)
        prob_aw   = _f("aw", attrs)
        conf_card = attrs.get("conf", "BAIXA")

        tip_m = re.search(r'class="tip-badge">([^<]+)<', block)
        tip   = tip_m.group(1).strip() if tip_m else ""

        # Picks por limiar de probabilidade — independente dos flags do football-dashboard
        pick_o25  = prob_o25  >= PICK_THRESH_O25
        pick_btts = prob_btts >= PICK_THRESH_BTTS

        # 1X2: apenas ALTA/MÉDIA, sem empate, direção do tip ou da probabilidade mais alta
        pick_dir = _extract_1x2_dir(tip)
        best_dir, best_prob = _best_1x2(prob_hw, prob_aw)
        pick_1x2  = conf_card in ("ALTA", "MÉDIA") and best_prob >= PICK_THRESH_1X2
        if pick_1x2 and pick_dir is None:
            pick_dir = best_dir  # fallback quando o tip não especifica direcção

        if not (pick_o25 or pick_btts or pick_1x2):
            continue

        games.append({
            "date":      attrs.get("date", ""),
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
            "prob_dr":   _f("dr", attrs),
            "prob_aw":   prob_aw,
            "xg_total":  _f("xgtotal", attrs),
        })

    return games


def analyze_today(history, dashboard_html):
    """Cruza picks de hoje e amanhã com estatísticas do backtest e devolve recomendações."""
    _now         = now_lisbon()
    today_str    = _now.strftime("%Y-%m-%d")
    tomorrow_str = (_now + timedelta(days=1)).strftime("%Y-%m-%d")
    records      = history.get("records", [])

    markets = [
        ("o25",  "pick_o25",  "hit_o25"),
        ("btts", "pick_btts", "hit_btts"),
        ("1x2",  "pick_1x2",  "hit_1x2"),
    ]

    # --- Backtest: estatísticas do corpus resolvido ---
    global_stats = {mk: segment_stats(records, pk, hk) for mk, pk, hk in markets}

    conf_stats = {}
    for conf in ("ALTA", "MÉDIA", "BAIXA"):
        subset = [r for r in records if r.get("conf") == conf]
        conf_stats[conf] = {mk: segment_stats(subset, pk, hk) for mk, pk, hk in markets}

    # --- Picks de hoje e amanhã ---
    today_games = parse_dashboard_html(dashboard_html, {today_str, tomorrow_str}) if dashboard_html else []
    print(f"[today] {len(today_games)} jogos com picks ({today_str} + {tomorrow_str})")

    today_leagues = {g["league"] for g in today_games}
    league_map: dict = {}
    for r in records:
        lg = r.get("league") or "Desconhecida"
        if lg in today_leagues:
            league_map.setdefault(lg, []).append(r)
    league_stats = {
        lg: {mk: segment_stats(recs, pk, hk) for mk, pk, hk in markets}
        for lg, recs in league_map.items()
    }

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

            kq = kelly_quarter(ref_wr, odds)

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
            "date":      g["date"],
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

    games_out.sort(key=lambda g: (g["date"], (g["ko_hour"] or "99:99").zfill(5)))

    tracker_db = record_and_resolve(games_out, records)
    perf       = tracker_stats(tracker_db)

    return {
        "today":        today_str,
        "tomorrow":     tomorrow_str,
        "total_games":  len(games_out),
        "total_picks":  sum(len(g["picks"]) for g in games_out),
        "strong_picks": sum(g["n_strong"] for g in games_out),
        "global_stats": global_stats,
        "conf_stats":   conf_stats,
        "backtest_n":   len(records),
        "games":        games_out,
        "tracker":      perf,
    }
