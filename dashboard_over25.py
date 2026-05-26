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


def _picks_table(picks):
    """Tabela de picks (resolvidos e pendentes)."""
    if not picks:
        return ""
    rows = ""
    for p in picks:
        result = p.get("result_over25") or ""
        if result == "WIN":
            badge = "<span style='color:#3fb950;font-weight:700'>WIN</span>"
        elif result == "LOSS":
            badge = "<span style='color:#f85149;font-weight:700'>LOSS</span>"
        else:
            badge = "<span style='color:#d29922'>Pendente</span>"

        casa  = p.get("casa") or "—"
        fora  = p.get("fora") or "—"
        liga  = p.get("liga") or "—"
        score = p.get("score_sistema") or "—"
        odds  = p.get("odds_over") or "—"
        xg    = p.get("xg_total") or "—"
        mov   = p.get("movimento") or "—"
        mov_c = "#3fb950" if mov == "SHORTENING" else ("#f0883e" if mov == "DRIFTING" else "#8b949e")
        sharp = p.get("sharp_label") or ""
        prob  = p.get("prob_over25") or ""
        prob_str = f"{float(prob):.0f}%" if prob else "—"

        rows += (
            f"<tr>"
            f"<td><b>{casa}</b> vs {fora}<br><span style='color:#8b949e;font-size:.78rem'>{liga}</span></td>"
            f"<td style='color:{mov_c}'>{mov}</td>"
            f"<td>{score}</td>"
            f"<td>{prob_str}</td>"
            f"<td>{odds}</td>"
            f"<td>{xg}</td>"
            f"<td style='color:#8b949e;font-size:.8rem'>{sharp}</td>"
            f"<td>{badge}</td>"
            f"</tr>"
        )
    return rows


def gen_dashboard_over25(stats):
    os.makedirs(DOCS_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    total    = stats.get("total", 0) if stats else 0
    resolved = stats.get("resolved", 0) if stats else 0

    # Sempre mostra dashboard, mesmo sem resultados ainda
    if not stats or total == 0:
        html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="UTF-8">
<title>Over 2.5 Scanner</title>
<style>body{{background:#0d1117;color:#8b949e;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}</style>
</head><body><p>Sem picks carregados — {now}</p></body></html>"""
        with open(f"{DOCS_DIR}/over25_dashboard.html", "w", encoding="utf-8") as f:
            f.write(html)
        return

    wr         = stats.get("win_rate", 0)
    roi        = stats.get("roi", 0)
    roi_pct    = stats.get("roi_pct", 0)
    streak     = stats.get("streak", 0)
    streak_type = stats.get("streak_type", "")
    clv        = stats.get("avg_clv")
    r7         = stats.get("recent_7d", {})

    # Gráficos — só quando há picks resolvidos
    charts_html = ""
    charts_js   = ""
    if resolved > 0:
        cum_roi_json    = json.dumps(stats.get("cumulative_roi", []))
        cum_labels_json = json.dumps(list(range(1, len(stats.get("cumulative_roi", [])) + 1)))
        daily           = stats.get("daily", {})
        last30          = list(daily.keys())[-30:]
        d_labels_json   = json.dumps(last30)
        d_roi_json      = json.dumps([round(daily[d]["roi"], 2) for d in last30])
        d_colors_json   = json.dumps(["rgba(63,185,80,.75)" if daily[d]["roi"] >= 0 else "rgba(248,81,73,.75)" for d in last30])

        charts_html = f"""
<div class="charts">
  <div class="card"><h3>ROI Acumulado</h3><canvas id="cRoi" height="160"></canvas></div>
  <div class="card"><h3>Performance Diária — últimos 30 dias</h3><canvas id="cDaily" height="160"></canvas></div>
</div>"""
        charts_js = f"""
const baseOpts = {{
  plugins: {{legend: {{display: false}}}},
  scales: {{ x: {{display: false}}, y: {{grid: {{color:'#21262d'}}, ticks: {{color:'#8b949e'}}}} }}
}};
new Chart(document.getElementById('cRoi').getContext('2d'), {{
  type:'line', data:{{labels:{cum_labels_json}, datasets:[{{data:{cum_roi_json},
  borderColor:'#58a6ff',backgroundColor:'rgba(88,166,255,.08)',borderWidth:2,pointRadius:0,fill:true,tension:.3}}]}},
  options:baseOpts
}});
new Chart(document.getElementById('cDaily').getContext('2d'), {{
  type:'bar', data:{{labels:{d_labels_json}, datasets:[{{data:{d_roi_json},
  backgroundColor:{d_colors_json},borderRadius:3}}]}},
  options:baseOpts
}});"""

    # KPIs — adaptar quando sem resultados
    if resolved > 0:
        clv_kpi = (
            f"<div class='kpi'><div class='kpi-l'>CLV Médio</div>"
            f"<div class='kpi-v' style='color:{_color(clv or 0)}'>{(clv or 0):+.2f}%</div></div>"
            if clv is not None else ""
        )
        kpi_bar = f"""
  <div class="kpi"><div class="kpi-l">Win Rate</div><div class="kpi-v" style="color:{_color(wr,.52)}">{_pct(wr)}</div></div>
  <div class="kpi"><div class="kpi-l">ROI Total</div><div class="kpi-v" style="color:{_color(roi)}">{roi:+.2f}u</div></div>
  <div class="kpi"><div class="kpi-l">Yield</div><div class="kpi-v" style="color:{_color(roi_pct)}">{roi_pct:+.1f}%</div></div>
  <div class="kpi"><div class="kpi-l">Streak</div><div class="kpi-v" style="color:{_color(1 if streak_type=='WIN' else -1)}">{'+' if streak_type=='WIN' else '-'}{streak}</div></div>
  {clv_kpi}
  <div class="kpi"><div class="kpi-l">WR 7 dias</div><div class="kpi-v" style="color:{_color(r7.get('win_rate',0),.52)}">{_pct(r7.get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">ROI 7 dias</div><div class="kpi-v" style="color:{_color(r7.get('roi',0))}">{r7.get('roi',0):+.2f}u</div></div>"""
    else:
        pending = stats.get("pending", total)
        kpi_bar = f"""
  <div class="kpi"><div class="kpi-l">Total Picks</div><div class="kpi-v" style="color:#58a6ff">{total}</div></div>
  <div class="kpi"><div class="kpi-l">Pendentes</div><div class="kpi-v" style="color:#d29922">{pending}</div></div>
  <div class="kpi"><div class="kpi-l">Resolvidos</div><div class="kpi-v" style="color:#8b949e">0</div></div>"""

    # Tabela breakdowns (só se houver resultados)
    breakdowns_html = ""
    if resolved > 0:
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
        breakdowns_html = (
            _table_card("Por Movimento de Odds", _breakdown_rows(stats.get("by_movement", {}))) +
            _table_card("Por Score do Sistema",  _breakdown_rows(stats.get("by_score", {}))) +
            _table_card("Por xG Total",          _breakdown_rows(stats.get("by_xg", {}))) +
            (f"""<div class="card"><h3>Por Liga</h3>
  <table><tr><th>Liga</th><th>Picks</th><th>WR</th><th>ROI</th></tr>{league_rows}</table>
</div>""" if league_rows else "")
        )

    # 1X2 sharp
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

    # Tabela de picks recentes/pendentes
    all_picks = stats.get("all_picks_raw", [])
    picks_rows = _picks_table(all_picks)
    pending_notice = "" if resolved > 0 else """
<div style="background:#1c2128;border:1px solid #d29922;border-radius:8px;padding:12px 16px;margin-bottom:16px;color:#d29922;font-size:.85rem;">
  ⏳ Sem resultados registados ainda — os picks abaixo estão pendentes de resultado.
  O dashboard de performance aparece assim que os primeiros resultados forem registados.
</div>"""

    script_tag = f"<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>" if resolved > 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Over 2.5 Scanner — Analista</title>
{script_tag}
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
td{{padding:5px 8px;border-bottom:1px solid #21262d;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
@media(max-width:650px){{.charts{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>🎯 Over 2.5 Scanner</h1>
<p class="sub">Actualizado: {now} · {resolved} resolvidos · {stats.get('pending', 0)} pendentes · {total} total</p>

{pending_notice}

<div class="kpi-bar">{kpi_bar}</div>

{charts_html}
{breakdowns_html}

<div class="card">
  <h3>Picks Recentes</h3>
  <table>
    <tr><th>Jogo</th><th>Mov.</th><th>Score</th><th>Prob</th><th>Odds</th><th>xG</th><th>Sharp</th><th>Result.</th></tr>
    {picks_rows if picks_rows else "<tr><td colspan='8' style='color:#8b949e;text-align:center'>Sem picks</td></tr>"}
  </table>
</div>

{p1x2_html}

<script>{charts_js}</script>
</body>
</html>"""

    with open(f"{DOCS_DIR}/over25_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] over25_dashboard.html gerado")
