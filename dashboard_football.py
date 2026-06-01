# dashboard_football.py — Gera docs/football_dashboard.html
import json
import os
from datetime import datetime, timezone
from utils import DOCS_DIR, pct, color, escape


def _brier_interp(bs):
    if bs < 0.15:
        return "excelente"
    if bs < 0.20:
        return "bom"
    if bs < 0.25:
        return "aceitável"
    return "fraco"


def _market_row(name, s):
    if s.get("picks", 0) == 0:
        return ""
    reliable = s.get("reliable", True)
    row_s    = "opacity:.6;font-style:italic" if not reliable else ""
    warn     = "<span style='color:oklch(48% 0.12 80);font-size:.68rem'> ⚠</span>" if not reliable else ""
    wrc      = color(s["win_rate"], 0.52) if reliable else "oklch(55% 0.014 82)"
    roic     = color(s["roi"]) if reliable else "oklch(55% 0.014 82)"
    ci_l     = s.get("ci_low", 0)
    ci_h     = s.get("ci_high", 1)
    ci_str   = f" <span style='font-size:.70rem;color:oklch(55% 0.014 82)'>[{ci_l:.0%}–{ci_h:.0%}]</span>"
    return (
        f"<tr style='{row_s}'><td><b>{escape(name)}</b>{warn}</td>"
        f"<td>{s['picks']}</td>"
        f"<td style='color:{wrc}'>{pct(s['win_rate'])}{ci_str}</td>"
        f"<td style='color:{roic}'>{s['roi']:+.0f}u ({s['roi_pct']:+.1f}%)</td></tr>"
    )


def gen_dashboard_football(stats):
    os.makedirs(DOCS_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if not stats or stats.get("total", 0) == 0:
        html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="UTF-8">
<title>Matemática Da Bola</title>
<style>body{{background:oklch(7% 0.006 95);color:oklch(63% 0.024 82);font-family:"Albert Sans","Avenir Next","Helvetica Neue",Arial,system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}</style>
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
    cum_1x2_json    = json.dumps(stats.get("cum_1x2_series", []))
    cum_treble_json = json.dumps(stats.get("cum_treble_series", []))

    daily  = stats.get("daily", {})
    last30 = list(daily.keys())[-30:]
    d_labels_json = json.dumps(last30)

    # Tabela por confiança com IC
    conf_rows = []
    for level in ["ALTA", "MÉDIA", "BAIXA"]:
        s = conf.get(level, {})
        if s.get("picks", 0) == 0:
            continue
        reliable = s.get("reliable", True)
        row_s    = "opacity:.6;font-style:italic" if not reliable else ""
        warn     = "<span style='color:oklch(48% 0.12 80);font-size:.68rem'> ⚠</span>" if not reliable else ""
        wrc      = color(s["win_rate"], 0.55) if reliable else "oklch(55% 0.014 82)"
        ci_l, ci_h = s.get("ci_low", 0), s.get("ci_high", 1)
        conf_rows.append(
            f"<tr style='{row_s}'><td><b>{level}</b>{warn}</td>"
            f"<td>{s['records']}</td>"
            f"<td>{s['picks']}</td>"
            f"<td style='color:{wrc}'>{pct(s['win_rate'])}"
            f" <span style='font-size:.70rem;color:oklch(55% 0.014 82)'>[{ci_l:.0%}–{ci_h:.0%}]</span></td></tr>"
        )
    conf_rows_html = "".join(conf_rows)

    # Tabela por liga com flag de fiabilidade
    league_rows = []
    for lg, s in stats.get("by_league", {}).items():
        o25c  = color(s["o25_wr"], 0.52)  if s.get("o25_reliable")  else "oklch(55% 0.014 82)"
        bttsc = color(s["btts_wr"], 0.55) if s.get("btts_reliable") else "oklch(55% 0.014 82)"
        o25w  = "" if s.get("o25_reliable")  else "<span style='color:oklch(48% 0.12 80);font-size:.68rem'>⚠</span>"
        bttsw = "" if s.get("btts_reliable") else "<span style='color:oklch(48% 0.12 80);font-size:.68rem'>⚠</span>"
        league_rows.append(
            f"<tr><td>{escape(lg)}</td><td>{s['records']}</td>"
            f"<td style='color:{o25c}'>{pct(s['o25_wr'])} ({s['o25_picks']}){o25w}</td>"
            f"<td style='color:{bttsc}'>{pct(s['btts_wr'])} ({s['btts_picks']}){bttsw}</td></tr>"
        )
    league_rows_html = "".join(league_rows)

    # Calibração O2.5 (reliability diagram como tabela)
    calib_rows = []
    for band in cal.get("o25", []):
        if band["n"] == 0 or band["actual"] is None:
            continue
        diff  = band["actual"] - band["predicted"]
        dc    = "oklch(70% 0.12 188)" if diff > 0.03 else ("oklch(58% 0.15 35)" if diff < -0.03 else "oklch(84% 0.035 82)")
        arrow = "↑" if diff > 0.03 else ("↓" if diff < -0.03 else "≈")
        calib_rows.append(
            f"<tr><td>{band['band']}</td>"
            f"<td>{band['n']}</td>"
            f"<td>{band['predicted']:.0%}</td>"
            f"<td style='color:{dc}'>{band['actual']:.0%} {arrow}</td>"
            f"<td style='color:{dc}'>{diff:+.1%}</td></tr>"
        )
    calib_rows_html = "".join(calib_rows)

    bs_o25  = bs.get("o25")
    bs_btts = bs.get("btts")
    brier_note = ""
    if bs_o25 is not None:
        interp = _brier_interp(bs_o25)
        brier_note = (f"<p style='color:oklch(63% 0.024 82);font-size:.72rem;margin-top:8px'>"
                      f"Brier Score O2.5: <b>{bs_o25:.4f}</b> ({interp})"
                      + (f" · BTTS: <b>{bs_btts:.4f}</b>" if bs_btts is not None else "")
                      + " — 0=perfeito, 0.25=aleatório</p>")

    calibration_card = ""
    if calib_rows_html:
        calibration_card = f"""
<div class="card">
  <h3>Calibração do Modelo — Reliability Diagram O2.5</h3>
  <table>
    <tr><th>Banda Prob</th><th>N</th><th>Previsto</th><th>Real</th><th>Desvio</th></tr>
    {calib_rows_html}
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
    tr_rel  = "" if tr.get("reliable") else "<span style='color:oklch(48% 0.12 80);font-size:.75rem'> ⚠ n&lt;10</span>"

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Matemática Da Bola — Analista</title>
<meta http-equiv="refresh" content="900">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Albert+Sans:wght@300;400;500;600&family=Alumni+Sans+Pinstripe&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:oklch(7% 0.006 95);color:oklch(81% 0.03 82);font-family:"Albert Sans","Avenir Next","Helvetica Neue",Arial,system-ui,sans-serif;padding:20px;font-size:14px}}
h1{{font-size:1.5rem;color:oklch(84% 0.19 80.46);margin-bottom:4px;font-family:"Alumni Sans Pinstripe","Albert Sans",sans-serif;font-weight:300;letter-spacing:.02em;}}
.sub{{color:oklch(63% 0.024 82);font-size:.82rem;margin-bottom:20px;font-family:"SFMono-Regular","Roboto Mono",Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;font-size:.72rem;}}
.kpi-bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}}
.kpi{{background:oklch(11% 0.006 95);border:1px solid oklch(28% 0.010 95);border-radius:2px;padding:12px 18px;min-width:120px}}
.kpi-l{{font-size:.72rem;color:oklch(63% 0.024 82);text-transform:uppercase;letter-spacing:.05em}}
.kpi-v{{font-size:1.5rem;font-weight:700;margin-top:3px}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:oklch(11% 0.006 95);border:1px solid oklch(28% 0.010 95);border-radius:2px;padding:16px;margin-bottom:14px}}
.card h3{{font-size:.82rem;color:oklch(63% 0.024 82);margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;color:oklch(63% 0.024 82);padding:5px 8px;border-bottom:1px solid oklch(28% 0.010 95);font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid oklch(15% 0.008 95)}}
tr:last-child td{{border-bottom:none}}
@media(max-width:560px){{.charts{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>⚽ Matemática Da Bola</h1>
<p class="sub">Actualizado: {now} · {stats['total']} registos · {stats['dates_processed']} dias processados</p>

<div class="kpi-bar">
  <div class="kpi"><div class="kpi-l">O2.5 WR</div><div class="kpi-v" style="color:{color(pm.get('o25',dict()).get('win_rate',0),.52)}">{pct(pm.get('o25',dict()).get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">BTTS WR</div><div class="kpi-v" style="color:{color(pm.get('btts',dict()).get('win_rate',0),.55)}">{pct(pm.get('btts',dict()).get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">1X2 WR</div><div class="kpi-v" style="color:{color(pm.get('1x2',dict()).get('win_rate',0),.52)}">{pct(pm.get('1x2',dict()).get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">1X2 ROI</div><div class="kpi-v" style="color:{color(pm.get('1x2',dict()).get('roi',0))}">{pm.get('1x2',dict()).get('roi',0):+.1f}u</div></div>
  <div class="kpi"><div class="kpi-l">Triplas WR</div><div class="kpi-v" style="color:{color(tr.get('win_rate',0),.3)}">{pct(tr.get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">Triplas ROI</div><div class="kpi-v" style="color:{color(tr.get('roi',0))}">{tr.get('roi',0):+.1f}u</div></div>
  <div class="kpi"><div class="kpi-l">O2.5 7d WR</div><div class="kpi-v" style="color:{color(r7_o25.get('win_rate',0),.52)}">{pct(r7_o25.get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">BTTS 7d WR</div><div class="kpi-v" style="color:{color(r7_btts.get('win_rate',0),.55)}">{pct(r7_btts.get('win_rate',0))}</div></div>
</div>

<div class="charts">
  <div class="card"><h3>ROI Acumulado — Over 2.5</h3><canvas id="cO25" height="160"></canvas></div>
  <div class="card"><h3>ROI Acumulado — BTTS</h3><canvas id="cBtts" height="160"></canvas></div>
  <div class="card"><h3>ROI Acumulado — 1X2</h3><canvas id="c1x2" height="160"></canvas></div>
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
  <p style="color:oklch(63% 0.024 82);font-size:.72rem;margin-top:8px">⚠ n&lt;20 = amostra insuficiente (itálico) · IC 95% Wilson entre parênteses rectos</p>
</div>

<div class="card">
  <h3>Calibração por Confiança</h3>
  <table>
    <tr><th>Nível</th><th>Jogos</th><th>Picks</th><th>WR (todos os mercados)</th></tr>
    {conf_rows_html}
  </table>
</div>

{calibration_card}

<div class="card">
  <h3>Sistema de Triplas — {tr.get('total', 0)} triplas ({tr.get('pending', 0)} pendentes)</h3>
  {'<p style="color:oklch(48% 0.12 80);font-size:.78rem;margin-bottom:8px">* Odds estimadas a partir das probabilidades do modelo (BSD API não guarda odds das triplas)</p>' if tr.get('odds_estimated') else ''}
  <table>
    <tr><th>Total</th><th>Ganhas</th><th>WR</th><th>ROI *</th><th>Odds médias *</th></tr>
    <tr>
      <td>{tr.get('total',0)}{tr_rel}</td>
      <td>{tr.get('won',0)}</td>
      <td style="color:{color(tr.get('win_rate',0),.3)}">{pct(tr.get('win_rate',0))}
        <span style='font-size:.72rem;color:oklch(55% 0.014 82)'>[{tr_ci_l:.0%}–{tr_ci_h:.0%}]</span></td>
      <td style="color:{color(tr.get('roi',0))}">{tr.get('roi',0):+.2f}u ({tr.get('roi_pct',0):+.1f}%)</td>
      <td>{tr.get('avg_odds',0):.2f}x</td>
    </tr>
  </table>
</div>

<div class="card">
  <h3>Por Liga</h3>
  <table>
    <tr><th>Liga</th><th>Jogos</th><th>O2.5 WR (picks)</th><th>BTTS WR (picks)</th></tr>
    {league_rows_html}
  </table>
</div>

<script>
const gridColor = '#232322', tickColor = '#989490';
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
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_o25_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_o25_json}, '#40b89a', 'rgba(64,184,154,.08)')]}}, options:lineOpts
}});
new Chart(document.getElementById('cBtts').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_btts_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_btts_json}, '#c9a030', 'rgba(201,160,48,.08)')]}}, options:lineOpts
}});
new Chart(document.getElementById('c1x2').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_1x2_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_1x2_json}, '#6a90c4', 'rgba(106,144,196,.08)')]}}, options:lineOpts
}});
new Chart(document.getElementById('cTreble').getContext('2d'), {{
  type:'line', data:{{labels: Array.from({{length:{len(stats.get('cum_treble_series',[]))}}},(_,i)=>i+1), datasets:[lineDataset({cum_treble_json}, '#b88a20', 'rgba(184,138,32,.08)')]}}, options:lineOpts
}});
</script>
</body>
</html>"""

    with open(f"{DOCS_DIR}/football_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] football_dashboard.html gerado")
