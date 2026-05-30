# dashboard_football.py — Gera docs/football_dashboard.html
import json
import os
from datetime import datetime, timezone

DOCS_DIR = "docs"


def _pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def _color(v, threshold=0.0):
    return "#3fb950" if v >= threshold else "#f85149"


def _market_row(name, s):
    if s.get("picks", 0) == 0:
        return ""
    reliable = s.get("reliable", True)
    row_s    = "opacity:.6;font-style:italic" if not reliable else ""
    warn     = "<span style='color:#d29922;font-size:.68rem'> ⚠</span>" if not reliable else ""
    wrc      = _color(s["win_rate"], 0.52) if reliable else "#6e7681"
    roic     = _color(s["roi"]) if reliable else "#6e7681"
    ci_l     = s.get("ci_low", 0)
    ci_h     = s.get("ci_high", 1)
    ci_str   = f" <span style='font-size:.70rem;color:#6e7681'>[{ci_l:.0%}–{ci_h:.0%}]</span>"
    return (
        f"<tr style='{row_s}'><td><b>{name}</b>{warn}</td>"
        f"<td>{s['picks']}</td>"
        f"<td style='color:{wrc}'>{_pct(s['win_rate'])}{ci_str}</td>"
        f"<td style='color:{roic}'>{s['roi']:+.0f}u ({s['roi_pct']:+.1f}%)</td></tr>"
    )


def gen_dashboard_football(stats):
    os.makedirs(DOCS_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if not stats or stats.get("total", 0) == 0:
        html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="UTF-8">
<title>Matemática Da Bola</title>
<style>body{{background:#0d1117;color:#8b949e;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}</style>
</head><body><p>Sem dados disponíveis — {now}</p></body></html>"""
        with open(f"{DOCS_DIR}/football_dashboard.html", "w", encoding="utf-8") as f:
            f.write(html)
        return

    pm   = stats.get("per_market", {})
    tr   = stats.get("trebles", {})
    r7   = stats.get("recent_7d", {})
    conf = stats.get("by_confidence", {})
    bs   = stats.get("brier_scores", {})
    cal  = stats.get("calibration", {})

    # JSON para gráficos
    cum_o25_json    = json.dumps(stats.get("cum_o25_series", []))
    cum_btts_json   = json.dumps(stats.get("cum_btts_series", []))
    cum_treble_json = json.dumps(stats.get("cum_treble_series", []))

    daily  = stats.get("daily", {})
    last30 = list(daily.keys())[-30:]
    d_labels_json = json.dumps(last30)

    # Tabela por confiança com IC
    conf_rows = ""
    for level in ["ALTA", "MÉDIA", "BAIXA"]:
        s = conf.get(level, {})
        if s.get("picks", 0) == 0:
            continue
        reliable = s.get("reliable", True)
        row_s    = "opacity:.6;font-style:italic" if not reliable else ""
        warn     = "<span style='color:#d29922;font-size:.68rem'> ⚠</span>" if not reliable else ""
        wrc      = _color(s["win_rate"], 0.55) if reliable else "#6e7681"
        ci_l, ci_h = s.get("ci_low", 0), s.get("ci_high", 1)
        conf_rows += (
            f"<tr style='{row_s}'><td><b>{level}</b>{warn}</td>"
            f"<td>{s['records']}</td>"
            f"<td>{s['picks']}</td>"
            f"<td style='color:{wrc}'>{_pct(s['win_rate'])}"
            f" <span style='font-size:.70rem;color:#6e7681'>[{ci_l:.0%}–{ci_h:.0%}]</span></td></tr>"
        )

    # Tabela por liga com flag de fiabilidade
    league_rows = ""
    for lg, s in stats.get("by_league", {}).items():
        o25c  = _color(s["o25_wr"], 0.52)  if s.get("o25_reliable")  else "#6e7681"
        bttsc = _color(s["btts_wr"], 0.55) if s.get("btts_reliable") else "#6e7681"
        o25w  = "" if s.get("o25_reliable")  else "<span style='color:#d29922;font-size:.68rem'>⚠</span>"
        bttsw = "" if s.get("btts_reliable") else "<span style='color:#d29922;font-size:.68rem'>⚠</span>"
        league_rows += (
            f"<tr><td>{lg}</td><td>{s['records']}</td>"
            f"<td style='color:{o25c}'>{_pct(s['o25_wr'])} ({s['o25_picks']}){o25w}</td>"
            f"<td style='color:{bttsc}'>{_pct(s['btts_wr'])} ({s['btts_picks']}){bttsw}</td></tr>"
        )

    # Calibração O2.5 (reliability diagram como tabela)
    calib_rows = ""
    for band in cal.get("o25", []):
        if band["n"] == 0 or band["actual"] is None:
            continue
        diff  = band["actual"] - band["predicted"]
        dc    = "#3fb950" if diff > 0.03 else ("#f85149" if diff < -0.03 else "#e6edf3")
        arrow = "↑" if diff > 0.03 else ("↓" if diff < -0.03 else "≈")
        calib_rows += (
            f"<tr><td>{band['band']}</td>"
            f"<td>{band['n']}</td>"
            f"<td>{band['predicted']:.0%}</td>"
            f"<td style='color:{dc}'>{band['actual']:.0%} {arrow}</td>"
            f"<td style='color:{dc}'>{diff:+.1%}</td></tr>"
        )

    bs_o25  = bs.get("o25")
    bs_btts = bs.get("btts")
    brier_note = ""
    if bs_o25 is not None:
        interp = "excelente" if bs_o25 < 0.15 else ("bom" if bs_o25 < 0.20 else ("aceitável" if bs_o25 < 0.25 else "fraco"))
        brier_note = (f"<p style='color:#8b949e;font-size:.72rem;margin-top:8px'>"
                      f"Brier Score O2.5: <b>{bs_o25:.4f}</b> ({interp})"
                      + (f" · BTTS: <b>{bs_btts:.4f}</b>" if bs_btts is not None else "")
                      + " — 0=perfeito, 0.25=aleatório</p>")

    calibration_card = ""
    if calib_rows:
        calibration_card = f"""
<div class="card">
  <h3>Calibração do Modelo — Reliability Diagram O2.5</h3>
  <table>
    <tr><th>Banda Prob</th><th>N</th><th>Previsto</th><th>Real</th><th>Desvio</th></tr>
    {calib_rows}
  </table>
  {brier_note}
</div>"""

    # KPIs 7d
    r7pm    = r7.get("per_market", {})
    r7_o25  = r7pm.get("o25",  {})
    r7_btts = r7pm.get("btts", {})

    # Triplas IC
    tr_ci_l = tr.get("ci_low", 0)
    tr_ci_h = tr.get("ci_high", 1)
    tr_rel  = "" if tr.get("reliable") else "<span style='color:#d29922;font-size:.75rem'> ⚠ n&lt;10</span>"

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Matemática Da Bola — Analista</title>
<meta http-equiv="refresh" content="900">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',sans-serif;padding:20px;font-size:14px}}
h1{{font-size:1.5rem;color:#58a6ff;margin-bottom:4px}}
.sub{{color:#8b949e;font-size:.82rem;margin-bottom:20px}}
.kpi-bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}}
.kpi{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 18px;min-width:120px}}
.kpi-l{{font-size:.72rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em}}
.kpi-v{{font-size:1.5rem;font-weight:700;margin-top:3px}}
.charts{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:14px}}
.card h3{{font-size:.82rem;color:#8b949e;margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;color:#8b949e;padding:5px 8px;border-bottom:1px solid #30363d;font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid #21262d}}
tr:last-child td{{border-bottom:none}}
@media(max-width:750px){{.charts{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>⚽ Matemática Da Bola</h1>
<p class="sub">Actualizado: {now} · {stats['total']} registos · {stats['dates_processed']} dias processados</p>

<div class="kpi-bar">
  <div class="kpi"><div class="kpi-l">O2.5 WR</div><div class="kpi-v" style="color:{_color(pm.get('o25',{}).get('win_rate',0),.52)}">{_pct(pm.get('o25',{}).get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">BTTS WR</div><div class="kpi-v" style="color:{_color(pm.get('btts',{}).get('win_rate',0),.55)}">{_pct(pm.get('btts',{}).get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">1X2 WR</div><div class="kpi-v" style="color:{_color(pm.get('1x2',{}).get('win_rate',0),.52)}">{_pct(pm.get('1x2',{}).get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">Triplas WR</div><div class="kpi-v" style="color:{_color(tr.get('win_rate',0),.3)}">{_pct(tr.get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">Triplas ROI</div><div class="kpi-v" style="color:{_color(tr.get('roi',0))}">{tr.get('roi',0):+.1f}u</div></div>
  <div class="kpi"><div class="kpi-l">O2.5 7d WR</div><div class="kpi-v" style="color:{_color(r7_o25.get('win_rate',0),.52)}">{_pct(r7_o25.get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">BTTS 7d WR</div><div class="kpi-v" style="color:{_color(r7_btts.get('win_rate',0),.55)}">{_pct(r7_btts.get('win_rate',0))}</div></div>
</div>

<div class="charts">
  <div class="card"><h3>ROI Acumulado — Over 2.5</h3><canvas id="cO25" height="160"></canvas></div>
  <div class="card"><h3>ROI Acumulado — BTTS</h3><canvas id="cBtts" height="160"></canvas></div>
  <div class="card"><h3>ROI Acumulado — Triplas</h3><canvas id="cTreble" height="160"></canvas></div>
</div>

<div class="card">
  <h3>Performance por Mercado</h3>
  <table>
    <tr><th>Mercado</th><th>Picks</th><th>Win Rate</th><th>ROI (flat)</th></tr>
    {_market_row("Over 2.5", pm.get("o25", {}))}
    {_market_row("BTTS", pm.get("btts", {}))}
    {_market_row("1X2", pm.get("1x2", {}))}
    {_market_row("xG", pm.get("xg", {}))}
  </table>
  <p style="color:#8b949e;font-size:.72rem;margin-top:8px">⚠ n&lt;20 = amostra insuficiente (itálico) · IC 95% Wilson entre parênteses rectos</p>
</div>

<div class="card">
  <h3>Calibração por Confiança</h3>
  <table>
    <tr><th>Nível</th><th>Jogos</th><th>Picks</th><th>WR (todos os mercados)</th></tr>
    {conf_rows}
  </table>
</div>

{calibration_card}

<div class="card">
  <h3>Sistema de Triplas — {tr.get('total', 0)} triplas ({tr.get('pending', 0)} pendentes)</h3>
  {'<p style="color:#d29922;font-size:.78rem;margin-bottom:8px">* Odds estimadas a partir das probabilidades do modelo (BSD API não guarda odds das triplas)</p>' if tr.get('odds_estimated') else ''}
  <table>
    <tr><th>Total</th><th>Ganhas</th><th>WR</th><th>ROI *</th><th>Odds médias *</th></tr>
    <tr>
      <td>{tr.get('total',0)}{tr_rel}</td>
      <td>{tr.get('won',0)}</td>
      <td style="color:{_color(tr.get('win_rate',0),.3)}">{_pct(tr.get('win_rate',0))}
        <span style='font-size:.72rem;color:#6e7681'>[{tr_ci_l:.0%}–{tr_ci_h:.0%}]</span></td>
      <td style="color:{_color(tr.get('roi',0))}">{tr.get('roi',0):+.2f}u ({tr.get('roi_pct',0):+.1f}%)</td>
      <td>{tr.get('avg_odds',0):.2f}x</td>
    </tr>
  </table>
</div>

<div class="card">
  <h3>Por Liga</h3>
  <table>
    <tr><th>Liga</th><th>Jogos</th><th>O2.5 WR (picks)</th><th>BTTS WR (picks)</th></tr>
    {league_rows}
  </table>
</div>

<script>
const gridColor = '#21262d', tickColor = '#8b949e';
const lineOpts = {{
  plugins: {{legend: {{display: false}}}},
  scales: {{
    x: {{display: false}},
    y: {{grid: {{color: gridColor}}, ticks: {{color: tickColor}}}}
  }}
}};

function lineDataset(data, color, bgColor) {{
  return {{
    data, borderColor: color, backgroundColor: bgColor || 'transparent',
    borderWidth: 2, pointRadius: 0, fill: true, tension: .3
  }};
}}

new Chart(document.getElementById('cO25').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_o25_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_o25_json}, '#3fb950', 'rgba(63,185,80,.08)')]}}, options:lineOpts
}});
new Chart(document.getElementById('cBtts').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_btts_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_btts_json}, '#f0883e', 'rgba(240,136,62,.08)')]}}, options:lineOpts
}});
new Chart(document.getElementById('cTreble').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_treble_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_treble_json}, '#a371f7', 'rgba(163,113,247,.08)')]}}, options:lineOpts
}});
</script>
</body>
</html>"""

    with open(f"{DOCS_DIR}/football_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] football_dashboard.html gerado")
