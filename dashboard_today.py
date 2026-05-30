# dashboard_today.py — Gera docs/today_dashboard.html ("Onde Apostar Hoje")
import os
from datetime import datetime, timezone

DOCS_DIR = "docs"


def _pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def _color(v, threshold=0.0):
    return "#3fb950" if v >= threshold else "#f85149"


def _edge_badge(edge):
    if edge == "strong":
        return "<span class='edge-badge edge-strong'>✅ Forte</span>"
    if edge == "moderate":
        return "<span class='edge-badge edge-moderate'>⚠️ Moderado</span>"
    if edge == "weak":
        return "<span class='edge-badge edge-weak'>❌ Fraco</span>"
    return "<span class='edge-badge edge-insuf'>📊 Dados insuf.</span>"


def _conf_badge(conf):
    styles = {
        "ALTA":  "background:#0d2818;color:#3fb950;border:1px solid #166534",
        "MÉDIA": "background:#1c1a00;color:#d29922;border:1px solid #7d6608",
        "BAIXA": "background:#1c0a0a;color:#f85149;border:1px solid #7f1d1d",
    }
    s = styles.get(conf, "background:#161b22;color:#8b949e;border:1px solid #30363d")
    return f"<span class='conf-badge' style='{s}'>{conf}</span>"


def _dir_label(d):
    return {"H": "Vitória Casa", "A": "Vitória Fora", "D": "Empate", None: ""}.get(d, "")


def _pick_card(pick):
    edge       = pick["edge"]
    label      = pick["label"]
    ref_label  = pick["ref_label"]
    ref_wr     = pick["ref_wr"]
    ref_n      = pick["ref_n"]
    ref_ci_l   = pick["ref_ci_l"]
    ref_ci_h   = pick["ref_ci_h"]
    global_wr  = pick["global_wr"]
    global_n   = pick["global_n"]
    league_n   = pick["league_n"]
    league_wr  = pick["league_wr"]
    kq         = pick["kelly_pct"]
    odds       = pick["odds"]

    border_color = {
        "strong":      "#166534",
        "moderate":    "#7d6608",
        "weak":        "#30363d",
        "insufficient": "#30363d",
    }.get(edge, "#30363d")
    bg_color = {
        "strong":  "#0d2818",
        "moderate": "#1c1a00",
    }.get(edge, "#161b22")

    dir_label = _dir_label(pick.get("dir"))
    market_title = f"{label}" + (f" <span style='font-size:.78rem;color:#8b949e'>({dir_label})</span>" if dir_label else "")

    # Stats line (ref)
    warn_n = "" if pick["ref_reliable"] else " <span style='color:#d29922;font-size:.72rem'>⚠ n&lt;20</span>"
    ref_src_label = ref_label if ref_label in ("ALTA", "MÉDIA", "BAIXA") else "global"
    ref_line = (f"<div class='stat-line'>"
                f"<span class='stat-key'>Backtest {ref_src_label}:</span>"
                f" <b style='color:{_color(ref_wr, 1/odds)}'>{_pct(ref_wr)}</b>"
                f" (n={ref_n})"
                f" <span style='color:#6e7681'>[{ref_ci_l:.0%}–{ref_ci_h:.0%}]</span>"
                f"{warn_n}</div>")

    # Global line (only if different from ref)
    global_line = ""
    if ref_label not in ("global",) and global_n >= 5:
        global_line = (f"<div class='stat-line'>"
                       f"<span class='stat-key'>Backtest global:</span>"
                       f" {_pct(global_wr)} (n={global_n})"
                       f"</div>")

    # League line
    league_line = ""
    if league_n >= 5:
        league_warn = " <span style='color:#d29922;font-size:.72rem'>⚠ n&lt;10</span>" if league_n < 10 else ""
        league_ci   = f" <span style='color:#6e7681'>[{pick['league_ci_l']:.0%}–{pick['league_ci_h']:.0%}]</span>" if league_n >= 5 else ""
        league_line = (f"<div class='stat-line'>"
                       f"<span class='stat-key'>Liga:</span>"
                       f" <b style='color:{_color(league_wr, 1/odds)}'>{_pct(league_wr)}</b>"
                       f" (n={league_n}){league_ci}{league_warn}</div>")

    # Kelly line
    kelly_line = ""
    if edge in ("strong", "moderate") and kq > 0:
        kelly_color = "#3fb950" if edge == "strong" else "#d29922"
        kelly_line  = (f"<div class='stat-line kelly-line'>"
                       f"<span class='stat-key'>Kelly ¼:</span>"
                       f" <b style='color:{kelly_color}'>{kq:.1f}% da banca</b>"
                       f" <span style='color:#6e7681'>(odds base {odds:.2f}x)</span>"
                       f"</div>")
    elif edge == "weak":
        kelly_line = "<div class='stat-line'><span style='color:#6e7681;font-size:.78rem'>EV negativo — sem recomendação de stake</span></div>"
    else:
        kelly_line = "<div class='stat-line'><span style='color:#6e7681;font-size:.78rem'>Dados insuficientes — sem recomendação</span></div>"

    return f"""
<div class='pick-block' style='background:{bg_color};border:1px solid {border_color};border-radius:8px;padding:12px 14px;margin-bottom:8px'>
  <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
    <span class='market-pill'>{market_title}</span>
    {_edge_badge(edge)}
  </div>
  {ref_line}
  {global_line}
  {league_line}
  {kelly_line}
</div>"""


def gen_dashboard_today(today_stats):
    os.makedirs(DOCS_DIR, exist_ok=True)
    now      = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    today_pt = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    backtest_n    = today_stats.get("backtest_n", 0)
    total_games   = today_stats.get("total_games", 0)
    total_picks   = today_stats.get("total_picks", 0)
    strong_picks  = today_stats.get("strong_picks", 0)
    games         = today_stats.get("games", [])
    global_stats  = today_stats.get("global_stats", {})
    conf_stats    = today_stats.get("conf_stats", {})

    # --- Backtest context table ---
    def _bt_row(market_key, label):
        gs = global_stats.get(market_key, {})
        rows = [f"<td style='padding:5px 10px;color:#8b949e;font-size:.78rem'>{label}</td>"]
        for conf in ("ALTA", "MÉDIA", "BAIXA"):
            cs = conf_stats.get(conf, {}).get(market_key, {})
            n  = cs.get("n", 0)
            wr = cs.get("win_rate", 0)
            ci_l = cs.get("ci_low", 0)
            ci_h = cs.get("ci_high", 1)
            if n >= 5:
                c    = _color(wr, 1 / {"o25": 1.90, "btts": 1.85, "1x2": 2.20}.get(market_key, 2.0))
                warn = " ⚠" if not cs.get("reliable") else ""
                rows.append(f"<td style='padding:5px 10px;color:{c}'>{_pct(wr)}<br><span style='color:#6e7681;font-size:.70rem'>(n={n}{warn}) [{ci_l:.0%}–{ci_h:.0%}]</span></td>")
            else:
                rows.append("<td style='padding:5px 10px;color:#6e7681;font-size:.78rem'>insuf.</td>")
        n_g  = gs.get("n", 0)
        wr_g = gs.get("win_rate", 0)
        ci_gl = gs.get("ci_low", 0)
        ci_gh = gs.get("ci_high", 1)
        if n_g >= 5:
            c    = _color(wr_g, 1 / {"o25": 1.90, "btts": 1.85, "1x2": 2.20}.get(market_key, 2.0))
            warn = " ⚠" if not gs.get("reliable") else ""
            rows.append(f"<td style='padding:5px 10px;color:{c}'><b>{_pct(wr_g)}</b><br><span style='color:#6e7681;font-size:.70rem'>(n={n_g}{warn}) [{ci_gl:.0%}–{ci_gh:.0%}]</span></td>")
        else:
            rows.append("<td style='padding:5px 10px;color:#6e7681;font-size:.78rem'>insuf.</td>")
        return "<tr>" + "".join(rows) + "</tr>"

    backtest_table = f"""
<div class='card'>
  <h3>Backtest — {backtest_n} jogos resolvidos · Base estatística das recomendações</h3>
  <table>
    <tr>
      <th style='padding:5px 10px'>Mercado</th>
      <th style='padding:5px 10px'>Confiança ALTA</th>
      <th style='padding:5px 10px'>Confiança MÉDIA</th>
      <th style='padding:5px 10px'>Confiança BAIXA</th>
      <th style='padding:5px 10px'>Global</th>
    </tr>
    {_bt_row("o25",  "Over 2.5")}
    {_bt_row("btts", "BTTS")}
    {_bt_row("1x2",  "1X2")}
  </table>
  <p style='color:#6e7681;font-size:.72rem;margin-top:8px'>
    ⚠ n&lt;20 = amostra insuficiente · IC = intervalo de confiança Wilson 95% ·
    Break-even: O2.5&nbsp;52.6%, BTTS&nbsp;54.1%, 1X2&nbsp;45.5%
  </p>
</div>"""

    # --- Game cards ---
    if not games:
        games_html = """
<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:32px;text-align:center;color:#8b949e'>
  <div style='font-size:2rem;margin-bottom:12px'>📭</div>
  <div style='font-size:1rem;color:#e6edf3'>Sem jogos com picks disponíveis para hoje</div>
  <div style='font-size:.82rem;margin-top:8px'>O pipeline do football-dashboard ainda não processou os jogos de hoje,<br>ou não há jogos nas ligas cobertas.</div>
</div>"""
    else:
        cards = []
        for g in games:
            # Game header
            conf_b = _conf_badge(g["conf"])
            ko     = f"🕐 {g['ko_hour']}:00" if g["ko_hour"] else ""
            picks_html = "".join(_pick_card(p) for p in g["picks"])

            # Model probabilities
            probs = []
            if g["prob_o25"] > 0:
                c = "#3fb950" if g["prob_o25"] >= 60 else "#8b949e"
                probs.append(f"<span style='color:{c}'>O2.5 <b>{g['prob_o25']:.0f}%</b></span>")
            if g["prob_btts"] > 0:
                c = "#3fb950" if g["prob_btts"] >= 60 else "#8b949e"
                probs.append(f"<span style='color:{c}'>BTTS <b>{g['prob_btts']:.0f}%</b></span>")
            if g["xg_total"] > 0:
                probs.append(f"<span style='color:#8b949e'>xG <b>{g['xg_total']:.1f}</b></span>")
            probs_html = (" · ".join(probs)) if probs else ""

            # 1X2 probabilities if relevant
            p1x2_html = ""
            if any(p["market"] == "1x2" for p in g["picks"]):
                dirs = []
                if g["prob_hw"]:
                    dirs.append(f"Casa {g['prob_hw']:.0f}%")
                if g["prob_dr"]:
                    dirs.append(f"Empate {g['prob_dr']:.0f}%")
                if g["prob_aw"]:
                    dirs.append(f"Fora {g['prob_aw']:.0f}%")
                if dirs:
                    p1x2_html = f"<div style='color:#8b949e;font-size:.78rem;margin-top:4px'>1X2: {' · '.join(dirs)}</div>"

            n_strong   = g["n_strong"]
            n_moderate = g["n_moderate"]
            card_border = "#166534" if n_strong > 0 else ("#7d6608" if n_moderate > 0 else "#30363d")

            cards.append(f"""
<div class='card' style='border-color:{card_border}'>
  <div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;margin-bottom:10px'>
    <div>
      <div style='font-size:.78rem;color:#8b949e;margin-bottom:3px'>{g['league']}</div>
      <div class='teams'><b>{g['home']}</b> <span style='color:#6e7681'>vs</span> <b>{g['away']}</b></div>
    </div>
    <div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap'>
      {conf_b}
      <span style='color:#8b949e;font-size:.8rem'>{ko}</span>
    </div>
  </div>
  {picks_html}
  <div style='margin-top:8px;font-size:.78rem;color:#6e7681'>{probs_html}{p1x2_html}</div>
</div>""")

        games_html = "\n".join(cards)

    # --- Summary strip ---
    summary_items = [
        f"<div class='kpi'><div class='kpi-l'>Jogos c/ Picks</div><div class='kpi-v' style='color:#58a6ff'>{total_games}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Total de Picks</div><div class='kpi-v' style='color:#8b949e'>{total_picks}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Apostas Fortes ✅</div><div class='kpi-v' style='color:#3fb950'>{strong_picks}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Apostas Moderadas ⚠️</div><div class='kpi-v' style='color:#d29922'>{sum(g['n_moderate'] for g in games)}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Backtest (jogos)</div><div class='kpi-v' style='color:#8b949e'>{backtest_n}</div></div>",
    ]
    summary_html = "\n".join(summary_items)

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Onde Apostar Hoje — Analista</title>
<meta http-equiv="refresh" content="900">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',sans-serif;padding:20px;font-size:14px}}
h1{{font-size:1.5rem;color:#58a6ff;margin-bottom:4px}}
.sub{{color:#8b949e;font-size:.82rem;margin-bottom:20px}}
.kpi-bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}}
.kpi{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 18px;min-width:130px}}
.kpi-l{{font-size:.72rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em}}
.kpi-v{{font-size:1.4rem;font-weight:700;margin-top:3px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;margin-bottom:16px}}
.card h3{{font-size:.80rem;color:#8b949e;margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;color:#8b949e;padding:5px 8px;border-bottom:1px solid #30363d;font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid #21262d;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
.teams{{font-size:1.05rem;color:#e6edf3}}
.conf-badge{{font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:12px}}
.market-pill{{font-size:.88rem;font-weight:700;color:#e6edf3}}
.edge-badge{{font-size:.72rem;padding:2px 8px;border-radius:10px;font-weight:600}}
.edge-strong{{background:#0d2818;color:#3fb950;border:1px solid #166534}}
.edge-moderate{{background:#1c1a00;color:#d29922;border:1px solid #7d6608}}
.edge-weak{{background:#1c0a0a;color:#f85149;border:1px solid #7f1d1d}}
.edge-insuf{{background:#161b22;color:#6e7681;border:1px solid #30363d}}
.stat-line{{font-size:.80rem;color:#8b949e;margin-bottom:3px;line-height:1.5}}
.stat-key{{color:#6e7681}}
.kelly-line{{margin-top:5px;padding-top:5px;border-top:1px solid #21262d}}
.legend{{background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:12px 16px;margin-bottom:20px;font-size:.78rem;color:#8b949e;line-height:1.7}}
@media(max-width:650px){{.kpi-bar{{gap:8px}}}}
</style>
</head>
<body>
<h1>🎯 Onde Apostar Hoje</h1>
<p class="sub">Actualizado: {now} · {today_pt} · picks do Matemática Da Bola qualificados pelo backtest</p>

<div class="kpi-bar">
{summary_html}
</div>

<div class="legend">
  <b>Como ler este dashboard:</b> O Matemática Da Bola identifica picks para os jogos do dia.
  O Analista cruza cada pick com o backtest histórico e atribui um sinal de edge:<br>
  ✅ <b>Forte</b> — IC inferior do backtest acima do break-even (evidência estatística de edge) ·
  ⚠️ <b>Moderado</b> — EV positivo mas IC ainda largo (aguardar mais dados) ·
  ❌ <b>Fraco</b> — EV negativo baseado no backtest ·
  📊 <b>Dados insuf.</b> — amostra muito pequena para conclusões.<br>
  Break-even: O2.5 52.6% · BTTS 54.1% · 1X2 45.5%. Kelly ¼ sobre odds base (sem odds reais de bookmaker).
</div>

{backtest_table}

<h2 style='color:#e6edf3;font-size:1rem;margin:20px 0 12px'>
  Jogos de Hoje — {total_games} com picks
  {'· <span style="color:#3fb950">' + str(strong_picks) + ' apostas fortes</span>' if strong_picks else ''}
</h2>

{games_html}

<p style='text-align:center;color:#6e7681;font-size:.75rem;margin-top:20px'>
  Analista · Baseado no backtest do Matemática Da Bola · nunovinhas-creator/Analista
</p>
</body>
</html>"""

    with open(f"{DOCS_DIR}/today_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] today_dashboard.html gerado")
