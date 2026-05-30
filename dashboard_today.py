# dashboard_today.py — Gera docs/today_dashboard.html ("Onde Apostar Hoje")
import json
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


_EDGE_LABELS = {
    "strong":      "✅ Forte",
    "moderate":    "⚠️ Moderado",
    "weak":        "❌ Fraco",
    "insufficient": "📊 Insuf.",
}
_MKT_LABELS = {"o25": "Over 2.5", "btts": "BTTS", "1x2": "1X2"}


def _tracker_section(perf):
    n       = perf["total_resolved"]
    pending = perf["total_pending"]

    if n == 0:
        return (
            f"<div class='card'>"
            f"<h3>Performance do Analista — Backtest Próprio</h3>"
            f"<div style='text-align:center;padding:24px;color:#8b949e'>"
            f"<div style='font-size:1.8rem;margin-bottom:10px'>📊</div>"
            f"<div style='color:#e6edf3'>A acumular dados — {pending} pick{'s' if pending != 1 else ''} pendente{'s' if pending != 1 else ''} de resolução</div>"
            f"<div style='font-size:.78rem;margin-top:8px'>As picks identificadas hoje são registadas e comparadas com os resultados reais assim que ficarem disponíveis.</div>"
            f"</div></div>"
        )

    wr      = perf["win_rate"]
    roi     = perf["roi"]
    roi_pct = perf["roi_pct"]
    wins    = perf["wins"]
    losses  = perf["losses"]
    wr_c    = "#3fb950" if wr >= 0.50 else "#f85149"
    roi_c   = "#3fb950" if roi >= 0   else "#f85149"

    TS  = "width:100%;border-collapse:collapse;font-size:.82rem"
    TH  = "text-align:left;color:#6e7681;padding:4px 8px;border-bottom:1px solid #21262d;font-weight:500"
    TD  = "padding:4px 8px;border-bottom:1px solid #21262d"
    TDN = "padding:4px 8px;border-bottom:1px solid #21262d;color:#8b949e"

    def _pos(v):
        return "#3fb950" if v >= 0 else "#f85149"

    def _wr_c(v):
        return "#3fb950" if v >= 0.50 else "#f85149"

    # -- Tabela por edge --
    edge_rows = ""
    for edge in ("strong", "moderate", "weak", "insufficient"):
        seg = perf["by_edge"].get(edge)
        if not seg:
            continue
        wr_e  = seg["win_rate"]
        rc    = _pos(seg["roi"])
        edge_rows += (
            f"<tr>"
            f"<td style='{TD}'>{_EDGE_LABELS.get(edge, edge)}</td>"
            f"<td style='{TDN}'>{seg['n']}</td>"
            f"<td style='{TD};color:{_wr_c(wr_e)};font-weight:600'>{wr_e:.1%}</td>"
            f"<td style='{TD};color:{rc}'>{seg['roi']:+.2f}u</td>"
            f"</tr>"
        )

    # -- Tabela por mercado --
    mkt_rows = ""
    for mkt in ("o25", "btts", "1x2"):
        seg = perf["by_market"].get(mkt)
        if not seg:
            continue
        wr_m = seg["win_rate"]
        rc   = _pos(seg["roi"])
        mkt_rows += (
            f"<tr>"
            f"<td style='{TD}'>{_MKT_LABELS.get(mkt, mkt)}</td>"
            f"<td style='{TDN}'>{seg['n']}</td>"
            f"<td style='{TD};color:{_wr_c(wr_m)};font-weight:600'>{wr_m:.1%}</td>"
            f"<td style='{TD};color:{rc}'>{seg['roi']:+.2f}u</td>"
            f"</tr>"
        )

    tables_html = (
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px'>"
        f"<div>"
        f"<div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px'>Por Sinal de Edge</div>"
        f"<table style='{TS}'>"
        f"<thead><tr><th style='{TH}'>Sinal</th><th style='{TH}'>n</th><th style='{TH}'>Acerto</th><th style='{TH}'>ROI</th></tr></thead>"
        f"<tbody>{edge_rows}</tbody></table>"
        f"</div>"
        f"<div>"
        f"<div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px'>Por Mercado</div>"
        f"<table style='{TS}'>"
        f"<thead><tr><th style='{TH}'>Mercado</th><th style='{TH}'>n</th><th style='{TH}'>Acerto</th><th style='{TH}'>ROI</th></tr></thead>"
        f"<tbody>{mkt_rows}</tbody></table>"
        f"</div>"
        f"</div>"
    )

    # -- Gráfico ROI acumulado --
    chart_html = ""
    series = perf.get("series", [])
    if len(series) >= 2:
        s_data     = json.dumps([s["cum"]  for s in series])
        s_tooltips = json.dumps([f"{s['date']} · {s['label']} ({s['market']}) {'✅' if s['hit'] else '❌'}"
                                  for s in series])
        s_labels   = json.dumps(list(range(1, len(series) + 1)))
        zero_arr   = json.dumps([0] * len(series))
        line_color = "#3fb950" if roi >= 0 else "#f85149"
        bg_color   = "rgba(63,185,80,0.07)" if roi >= 0 else "rgba(248,81,73,0.07)"
        chart_html = f"""
<div style='margin-bottom:18px'>
  <div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px'>ROI Acumulado ({n} picks resolvidas)</div>
  <canvas id='trackerChart' height='80'></canvas>
</div>
<script>
(function(){{
  var tooltips = {s_tooltips};
  var ctx = document.getElementById('trackerChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {s_labels},
      datasets: [
        {{
          label: 'ROI Acumulado (u)',
          data: {s_data},
          borderColor: '{line_color}',
          backgroundColor: '{bg_color}',
          fill: true,
          tension: 0.15,
          pointRadius: {3 if len(series) <= 50 else 0},
          pointHoverRadius: 5,
          borderWidth: 2,
        }},
        {{
          label: '',
          data: {zero_arr},
          borderColor: '#30363d',
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
          borderWidth: 1,
        }}
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            title: function(items) {{ return tooltips[items[0].dataIndex] || ''; }},
            label: function(item) {{ return 'ROI: ' + item.raw.toFixed(2) + 'u'; }}
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#8b949e', maxTicksLimit: 12 }}, grid: {{ color: '#21262d' }} }},
        y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});
}})();
</script>"""

    # -- Tabela de picks recentes --
    recent = perf.get("recent", [])
    recent_rows = ""
    for p in recent[:15]:
        hit_s   = "✅" if p.get("hit") else "❌"
        profit  = (p["odds"] - 1) if p.get("hit") else -1.0
        p_color = "#3fb950" if profit > 0 else "#f85149"
        edge_s  = _EDGE_LABELS.get(p.get("edge", ""), p.get("edge", ""))
        recent_rows += (
            f"<tr>"
            f"<td style='color:#8b949e'>{p.get('date','')}</td>"
            f"<td>{p.get('home','')} vs {p.get('away','')}</td>"
            f"<td style='color:#8b949e'>{_MKT_LABELS.get(p.get('market',''), p.get('market',''))}</td>"
            f"<td style='font-size:.75rem'>{edge_s}</td>"
            f"<td style='text-align:center;font-size:1.05rem'>{hit_s}</td>"
            f"<td style='color:{p_color};text-align:right'>{profit:+.2f}u</td>"
            f"</tr>"
        )

    recent_html = ""
    if recent_rows:
        recent_html = (
            f"<div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px'>Picks Recentes</div>"
            f"<div style='overflow-x:auto'><table style='{TS}'>"
            f"<thead><tr>"
            f"<th style='{TH}'>Data</th>"
            f"<th style='{TH}'>Jogo</th>"
            f"<th style='{TH}'>Mercado</th>"
            f"<th style='{TH}'>Edge</th>"
            f"<th style='{TH};text-align:center'>Res.</th>"
            f"<th style='{TH};text-align:right'>P&L</th>"
            f"</tr></thead>"
            f"<tbody>{recent_rows}</tbody>"
            f"</table></div>"
            f"<p style='font-size:.70rem;color:#6e7681;margin-top:6px'>ROI calculado com odds-base por mercado (O2.5 1.90x · BTTS 1.85x · 1X2 2.20x) · 1u por pick</p>"
        )

    return (
        f"<div class='card'>"
        f"<h3>Performance do Analista — Backtest Próprio · {n} resolvidas · {pending} pendentes</h3>"
        f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px;font-size:.90rem'>"
        f"<div>Taxa de Acerto: <b style='color:{wr_c}'>{wr:.1%}</b> <span style='color:#6e7681'>({wins}W / {losses}L)</span></div>"
        f"<div>ROI: <b style='color:{roi_c}'>{roi:+.2f}u</b> <span style='color:#6e7681'>({roi_pct:+.1f}%/pick)</span></div>"
        f"</div>"
        f"{tables_html}"
        f"{chart_html}"
        f"{recent_html}"
        f"</div>"
    )


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
    tracker       = today_stats.get("tracker", {"total_resolved": 0, "total_pending": 0})

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

    # --- Tracker KPIs ---
    t_n       = tracker.get("total_resolved", 0)
    t_pending = tracker.get("total_pending",  0)
    t_wr      = tracker.get("win_rate",  0.0)
    t_roi     = tracker.get("roi",       0.0)
    t_wr_c    = "#3fb950" if t_wr >= 0.50 else ("#8b949e" if t_n == 0 else "#f85149")
    t_roi_c   = "#3fb950" if t_roi >= 0   else ("#8b949e" if t_n == 0 else "#f85149")
    t_wr_s    = f"{t_wr:.1%}" if t_n > 0 else "—"
    t_roi_s   = f"{t_roi:+.2f}u" if t_n > 0 else "—"

    tracker_section_html = _tracker_section(tracker)

    # --- Summary strip ---
    summary_items = [
        f"<div class='kpi'><div class='kpi-l'>Jogos c/ Picks</div><div class='kpi-v' style='color:#58a6ff'>{total_games}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Fortes ✅</div><div class='kpi-v' style='color:#3fb950'>{strong_picks}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Moderadas ⚠️</div><div class='kpi-v' style='color:#d29922'>{sum(g['n_moderate'] for g in games)}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Rastreadas</div><div class='kpi-v' style='color:#8b949e'>{t_n + t_pending}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Acerto Próprio</div><div class='kpi-v' style='color:{t_wr_c}'>{t_wr_s}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>ROI Próprio</div><div class='kpi-v' style='color:{t_roi_c}'>{t_roi_s}</div></div>",
    ]
    summary_html = "\n".join(summary_items)

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Onde Apostar Hoje — Analista</title>
<meta http-equiv="refresh" content="900">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
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

{tracker_section_html}

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
