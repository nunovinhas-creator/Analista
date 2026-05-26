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
    if s["picks"] == 0:
        return ""
    wrc  = _color(s["win_rate"], 0.52)
    roic = _color(s["roi"])
    return (
        f"<tr><td><b>{name}</b></td>"
        f"<td>{s['picks']}</td>"
        f"<td style='color:{wrc}'>{_pct(s['win_rate'])}</td>"
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

    # Melhor mercado por WR
    best_market = max(pm.items(), key=lambda x: x[1]["win_rate"] if x[1]["picks"] > 0 else 0, default=("—", {}))

    # JSON para gráficos
    cum_o25_json    = json.dumps(stats.get("cum_o25_series", []))
    cum_btts_json   = json.dumps(stats.get("cum_btts_series", []))
    cum_treble_json = json.dumps(stats.get("cum_treble_series", []))

    daily = stats.get("daily", {})
    last30 = list(daily.keys())[-30:]
    d_labels_json = json.dumps(last30)
    d_o25_json  = json.dumps([round(daily[d]["o25_wins"] / daily[d]["o25_picks"] * 100 if daily[d]["o25_picks"] else 0, 1) for d in last30])
    d_btts_json = json.dumps([round(daily[d]["btts_wins"] / daily[d]["btts_picks"] * 100 if daily[d]["btts_picks"] else 0, 1) for d in last30])

    # Tabela por confiança
    conf_rows = ""
    for level in ["ALTA", "MÉDIA", "BAIXA"]:
        s = conf.get(level, {})
        if s.get("picks", 0) == 0:
            continue
        wrc = _color(s["win_rate"], 0.55)
        conf_rows += (
            f"<tr><td><b>{level}</b></td>"
            f"<td>{s['records']}</td>"
            f"<td>{s['picks']}</td>"
            f"<td style='color:{wrc}'>{_pct(s['win_rate'])}</td></tr>"
        )

    # Tabela por liga
    league_rows = ""
    for lg, s in stats.get("by_league", {}).items():
        o25c  = _color(s["o25_wr"], 0.52)
        bttsc = _color(s["btts_wr"], 0.55)
        league_rows += (
            f"<tr><td>{lg}</td><td>{s['records']}</td>"
            f"<td style='color:{o25c}'>{_pct(s['o25_wr'])} ({s['o25_picks']})</td>"
            f"<td style='color:{bttsc}'>{_pct(s['btts_wr'])} ({s['btts_picks']})</td></tr>"
        )

    # KPIs recentes 7d
    r7pm = r7.get("per_market", {})
    r7_o25  = r7pm.get("o25",  {})
    r7_btts = r7pm.get("btts", {})

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Matemática Da Bola — Analista</title>
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
</div>

<div class="card">
  <h3>Calibração por Confiança</h3>
  <table>
    <tr><th>Nível</th><th>Jogos</th><th>Picks</th><th>WR (todos os mercados)</th></tr>
    {conf_rows}
  </table>
</div>

<div class="card">
  <h3>Sistema de Triplas — {tr.get('total', 0)} triplas ({tr.get('pending', 0)} pendentes)</h3>
  {'<p style="color:#d29922;font-size:.78rem;margin-bottom:8px">* Odds estimadas a partir das probabilidades do modelo (BSD API não guarda odds das triplas)</p>' if tr.get('odds_estimated') else ''}
  <table>
    <tr><th>Total</th><th>Ganhas</th><th>WR</th><th>ROI *</th><th>Odds médias *</th></tr>
    <tr>
      <td>{tr.get('total',0)}</td>
      <td>{tr.get('won',0)}</td>
      <td style="color:{_color(tr.get('win_rate',0),.3)}">{_pct(tr.get('win_rate',0))}</td>
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

function lineDataset(data, color) {{
  return {{
    data, borderColor: color, backgroundColor: color.replace(')', ', .08)').replace('rgb', 'rgba'),
    borderWidth: 2, pointRadius: 0, fill: true, tension: .3
  }};
}}

new Chart(document.getElementById('cO25').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_o25_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_o25_json}, '#3fb950')]}}, options:lineOpts
}});
new Chart(document.getElementById('cBtts').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_btts_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_btts_json}, '#f0883e')]}}, options:lineOpts
}});
new Chart(document.getElementById('cTreble').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_treble_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_treble_json}, '#a371f7')]}}, options:lineOpts
}});
</script>
</body>
</html>"""

    with open(f"{DOCS_DIR}/football_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] football_dashboard.html gerado")
