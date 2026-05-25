# dashboard_over25.py — Gera docs/over25_dashboard.html
import json
import os
from datetime import datetime, timezone

DOCS_DIR = "docs"
PAGES_BASE = "https://nunovinhas-creator.github.io/Analista"


def _pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def _color(v, threshold=0.0):
    return "#3fb950" if v >= threshold else "#f85149"


def _breakdown_rows(data: dict):
    rows = ""
    for label, s in data.items():
        if s["count"] == 0:
            continue
        wrc = _color(s["win_rate"], 0.52)
        roic = _color(s.get("roi", 0), 0)
        rows += (
            f"<tr><td>{label}</td>"
            f"<td>{s['count']}</td>"
            f"<td style='color:{wrc}'>{_pct(s['win_rate'])}</td>"
            f"<td style='color:{roic}'>{s.get('roi', 0):+.2f}u ({s.get('roi_pct', 0):+.1f}%)</td></tr>"
        )
    return rows


def _table_card(title, rows_html):
    if not rows_html:
        return ""
    return f"""
<div class="card">
  <h3>{title}</h3>
  <table>
    <tr><th>Segmento</th><th>Picks</th><th>WR</th><th>ROI</th></tr>
    {rows_html}
  </table>
</div>"""


def gen_dashboard_over25(stats):
    os.makedirs(DOCS_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if not stats or stats.get("resolved", 0) == 0:
        html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="UTF-8">
<title>Over 2.5 Scanner</title>
<style>body{{background:#0d1117;color:#8b949e;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}</style>
</head><body><p>Sem dados disponíveis — {now}</p></body></html>"""
        with open(f"{DOCS_DIR}/over25_dashboard.html", "w", encoding="utf-8") as f:
            f.write(html)
        return

    wr = stats["win_rate"]
    roi = stats["roi"]
    roi_pct = stats["roi_pct"]
    streak = stats["streak"]
    streak_type = stats.get("streak_type", "")
    clv = stats.get("avg_clv")
    r7 = stats["recent_7d"]

    cum_roi_json = json.dumps(stats.get("cumulative_roi", []))
    cum_labels_json = json.dumps(list(range(1, len(stats.get("cumulative_roi", [])) + 1)))

    daily = stats.get("daily", {})
    last30 = list(daily.keys())[-30:]
    daily_labels_json = json.dumps(last30)
    daily_roi_json = json.dumps([round(daily[d]["roi"], 2) for d in last30])
    daily_colors_json = json.dumps(["rgba(63,185,80,.75)" if daily[d]["roi"] >= 0 else "rgba(248,81,73,.75)" for d in last30])

    clv_html = (
        f"<div class='kpi'><div class='kpi-l'>CLV Médio</div>"
        f"<div class='kpi-v' style='color:{_color(clv or 0)}'>{(clv or 0):+.2f}%</div></div>"
        if clv is not None else ""
    )

    picks_1x2 = stats.get("picks_1x2", {})
    p1x2_html = ""
    if picks_1x2.get("resolved", 0) > 0:
        p1x2_html = f"""
<div class="card">
  <h3>Sharp 1X2</h3>
  <table>
    <tr><th>Picks</th><th>WR</th><th>ROI</th><th>Yield</th></tr>
    <tr>
      <td>{picks_1x2["resolved"]}</td>
      <td style="color:{_color(picks_1x2['win_rate'], 0.52)}">{_pct(picks_1x2['win_rate'])}</td>
      <td style="color:{_color(picks_1x2['roi'])}">{picks_1x2['roi']:+.2f}u</td>
      <td style="color:{_color(picks_1x2['roi_pct'])}">{picks_1x2['roi_pct']:+.1f}%</td>
    </tr>
  </table>
</div>"""

    league_rows = ""
    for lg, s in stats.get("by_league", {}).items():
        if s["count"] == 0:
            continue
        lg_wrc  = _color(s["win_rate"], 0.52)
        lg_roic = _color(s.get("roi", 0))
        lg_roi  = s.get("roi", 0)
        league_rows += (
            f"<tr><td>{lg}</td><td>{s['count']}</td>"
            f"<td style='color:{lg_wrc}'>{_pct(s['win_rate'])}</td>"
            f"<td style='color:{lg_roic}'>{lg_roi:+.2f}u</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Over 2.5 Scanner — Analista</title>
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
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:14px}}
.card h3{{font-size:.82rem;color:#8b949e;margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;color:#8b949e;padding:5px 8px;border-bottom:1px solid #30363d;font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid #21262d}}
tr:last-child td{{border-bottom:none}}
@media(max-width:650px){{.charts{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>🎯 Over 2.5 Scanner</h1>
<p class="sub">Actualizado: {now} · {stats["resolved"]} picks resolvidos · {stats["pending"]} pendentes</p>

<div class="kpi-bar">
  <div class="kpi"><div class="kpi-l">Win Rate</div><div class="kpi-v" style="color:{_color(wr,.52)}">{_pct(wr)}</div></div>
  <div class="kpi"><div class="kpi-l">ROI Total</div><div class="kpi-v" style="color:{_color(roi)}">{roi:+.2f}u</div></div>
  <div class="kpi"><div class="kpi-l">Yield</div><div class="kpi-v" style="color:{_color(roi_pct)}">{roi_pct:+.1f}%</div></div>
  <div class="kpi"><div class="kpi-l">Streak</div><div class="kpi-v" style="color:{_color(1 if streak_type=='WIN' else -1)}">{'+' if streak_type=='WIN' else '-'}{streak}</div></div>
  {clv_html}
  <div class="kpi"><div class="kpi-l">WR 7 dias</div><div class="kpi-v" style="color:{_color(r7['win_rate'],.52)}">{_pct(r7['win_rate'])}</div></div>
  <div class="kpi"><div class="kpi-l">ROI 7 dias</div><div class="kpi-v" style="color:{_color(r7['roi'])}">{r7['roi']:+.2f}u</div></div>
</div>

<div class="charts">
  <div class="card"><h3>ROI Acumulado</h3><canvas id="cRoi" height="160"></canvas></div>
  <div class="card"><h3>Performance Diária — últimos 30 dias</h3><canvas id="cDaily" height="160"></canvas></div>
</div>

{_table_card("Por Movimento de Odds", _breakdown_rows(stats.get("by_movement", {})))}
{_table_card("Por Score do Sistema", _breakdown_rows(stats.get("by_score", {})))}
{_table_card("Por xG Total", _breakdown_rows(stats.get("by_xg", {})))}

<div class="card">
  <h3>Por Liga</h3>
  <table>
    <tr><th>Liga</th><th>Picks</th><th>WR</th><th>ROI</th></tr>
    {league_rows}
  </table>
</div>

{p1x2_html}

<script>
const gridColor = '#21262d';
const tickColor = '#8b949e';
const baseOpts = {{
  plugins: {{legend: {{display: false}}}},
  scales: {{
    x: {{display: false}},
    y: {{grid: {{color: gridColor}}, ticks: {{color: tickColor}}}}
  }}
}};

new Chart(document.getElementById('cRoi').getContext('2d'), {{
  type: 'line',
  data: {{
    labels: {cum_labels_json},
    datasets: [{{
      data: {cum_roi_json},
      borderColor: '#58a6ff',
      backgroundColor: 'rgba(88,166,255,.08)',
      borderWidth: 2, pointRadius: 0, fill: true, tension: .3
    }}]
  }},
  options: baseOpts
}});

new Chart(document.getElementById('cDaily').getContext('2d'), {{
  type: 'bar',
  data: {{
    labels: {daily_labels_json},
    datasets: [{{
      data: {daily_roi_json},
      backgroundColor: {daily_colors_json},
      borderRadius: 3
    }}]
  }},
  options: baseOpts
}});
</script>
</body>
</html>"""

    with open(f"{DOCS_DIR}/over25_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[dashboard] over25_dashboard.html gerado")
