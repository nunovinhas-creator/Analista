# dashboard_over25.py — Gera docs/over25_dashboard.html
import json
import os
from datetime import datetime, timezone

DOCS_DIR = "docs"

_MOV_COLORS = {"SHORTENING": "#3fb950", "DRIFTING": "#f0883e"}


def _pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def _color(v, threshold=0.0):
    return "#3fb950" if v >= threshold else "#f85149"


def _breakdown_rows(data: dict):
    """Linhas de tabela com indicador de fiabilidade (n<20) e IC Wilson."""
    rows = ""
    for label, s in data.items():
        if s["count"] == 0:
            continue
        reliable  = s.get("reliable", True)
        row_style = "opacity:.55;font-style:italic" if not reliable else ""
        warn_tag  = ("<span style='color:#d29922;font-size:.68rem;margin-left:3px' "
                     "title='Menos de 20 picks resolvidos'>⚠ n&lt;20</span>") if not reliable else ""
        wrc  = _color(s["win_rate"], 0.52) if reliable else "#6e7681"
        roic = _color(s.get("roi", 0), 0)  if reliable else "#6e7681"
        ci_str = ""
        if s.get("ci_low") is not None:
            ci_str = (f" <span style='font-size:.70rem;color:#6e7681'>"
                      f"[{s['ci_low']:.0%}–{s['ci_high']:.0%}]</span>")
        rows += (
            f"<tr style='{row_style}'>"
            f"<td>{label}{warn_tag}</td>"
            f"<td>{s['count']}</td>"
            f"<td style='color:{wrc}'>{_pct(s['win_rate'])}{ci_str}</td>"
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

        casa  = p.get("casa")  or "—"
        fora  = p.get("fora")  or "—"
        liga  = p.get("liga")  or "—"
        score = p.get("score_sistema") or "—"
        odds  = p.get("odds_over")     or "—"
        xg    = p.get("xg_total")      or "—"
        mov   = p.get("movimento")     or "—"
        mov_c = _MOV_COLORS.get(mov, "#8b949e")
        sharp = p.get("sharp_label")   or ""

        rows += (
            f"<tr>"
            f"<td><b>{casa}</b> vs {fora}<br><span style='color:#8b949e;font-size:.78rem'>{liga}</span></td>"
            f"<td style='color:{mov_c}'>{mov}</td>"
            f"<td>{score}</td>"
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

    if not stats or total == 0:
        html = f"""<!DOCTYPE html><html lang="pt"><head><meta charset="UTF-8">
<title>Over 2.5 Scanner</title>
<style>body{{background:#0d1117;color:#8b949e;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}}</style>
</head><body><p>Sem picks carregados — {now}</p></body></html>"""
        with open(f"{DOCS_DIR}/over25_dashboard.html", "w", encoding="utf-8") as f:
            f.write(html)
        return

    wr          = stats.get("win_rate", 0)
    roi         = stats.get("roi", 0)
    roi_pct     = stats.get("roi_pct", 0)
    streak      = stats.get("streak", 0)
    streak_type = stats.get("streak_type", "")
    clv         = stats.get("avg_clv")
    max_dd      = stats.get("max_drawdown", 0)
    ci_low      = stats.get("ci_low", 0)
    ci_high     = stats.get("ci_high", 1)
    r7          = stats.get("recent_7d", {})

    # Alerta CLV — construído fora do f-string
    clv_alert = ""
    if clv is not None and clv < -1:
        clv_alert = (
            "<div style='background:#1c2128;border:1px solid #f85149;border-radius:8px;"
            "padding:12px 16px;margin-bottom:16px;color:#f85149;font-size:.85rem;'>"
            f"<b>⚠️ CLV Médio: {clv:+.2f}%</b> — as odds fecham acima da entrada. "
            "Sistema a apostar depois do mercado mover. "
            "Apostar mais cedo após publicação do pick para capturar edge real."
            "</div>"
        )
    elif clv is not None and clv >= 2:
        clv_alert = (
            "<div style='background:#1c2128;border:1px solid #3fb950;border-radius:8px;"
            "padding:12px 16px;margin-bottom:16px;color:#3fb950;font-size:.85rem;'>"
            f"<b>✅ CLV Médio: {clv:+.2f}%</b> — apostas a ser feitas antes do mercado mover. Edge real confirmado."
            "</div>"
        )

    # Gráficos
    charts_html = ""
    charts_js   = ""
    if resolved > 0:
        cum_roi_json    = json.dumps(stats.get("cumulative_roi", []))
        cum_labels_json = json.dumps(list(range(1, len(stats.get("cumulative_roi", [])) + 1)))
        rolling_wr_json = json.dumps(stats.get("rolling_wr_series", []))
        daily           = stats.get("daily", {})
        last30          = list(daily.keys())[-30:]
        d_labels_json   = json.dumps(last30)
        d_roi_json      = json.dumps([round(daily[d]["roi"], 2) for d in last30])
        d_colors_json   = json.dumps(["rgba(63,185,80,.75)" if daily[d]["roi"] >= 0 else "rgba(248,81,73,.75)" for d in last30])

        charts_html = """
<div class="charts">
  <div class="card"><h3>ROI Acumulado + WR Móvel (20 picks)</h3><canvas id="cRoi" height="160"></canvas></div>
  <div class="card"><h3>Performance Diária — últimos 30 dias</h3><canvas id="cDaily" height="160"></canvas></div>
</div>"""

        charts_js = f"""
new Chart(document.getElementById('cRoi').getContext('2d'), {{
  type:'line',
  data:{{
    labels:{cum_labels_json},
    datasets:[
      {{data:{cum_roi_json},label:'ROI',borderColor:'#58a6ff',backgroundColor:'rgba(88,166,255,.08)',
       borderWidth:2,pointRadius:0,fill:true,tension:.3,yAxisID:'y'}},
      {{data:{rolling_wr_json},label:'WR Móvel',borderColor:'#f0883e',borderWidth:1.5,
       pointRadius:0,tension:.3,fill:false,yAxisID:'y1',borderDash:[4,2]}}
    ]
  }},
  options:{{
    plugins:{{legend:{{display:true,labels:{{color:'#8b949e',boxWidth:12,font:{{size:11}}}}}}}},
    scales:{{
      x:{{display:false}},
      y:{{grid:{{color:'#21262d'}},ticks:{{color:'#8b949e'}}}},
      y1:{{position:'right',min:0,max:1,grid:{{display:false}},
           ticks:{{color:'#f0883e',callback:function(v){{return (v*100).toFixed(0)+'%'}}}}}}
    }}
  }}
}});
new Chart(document.getElementById('cDaily').getContext('2d'), {{
  type:'bar',
  data:{{labels:{d_labels_json},datasets:[{{data:{d_roi_json},backgroundColor:{d_colors_json},borderRadius:3}}]}},
  options:{{plugins:{{legend:{{display:false}}}},scales:{{x:{{display:false}},y:{{grid:{{color:'#21262d'}},ticks:{{color:'#8b949e'}}}}}}}}
}});"""

    # KPI bar
    dd_color = "#3fb950" if max_dd == 0 else ("#d29922" if max_dd < 5 else "#f85149")
    ci_str   = (f"<span style='font-size:.72rem;color:#6e7681;display:block;margin-top:1px'>"
                f"[{ci_low:.0%}–{ci_high:.0%}]</span>") if resolved > 0 else ""

    if resolved > 0:
        clv_kpi = ""
        if clv is not None:
            clv_kpi = (f"<div class='kpi'><div class='kpi-l'>CLV Médio</div>"
                       f"<div class='kpi-v' style='color:{_color(clv or 0)}'>{(clv or 0):+.2f}%</div></div>")
        kpi_bar = f"""
  <div class="kpi"><div class="kpi-l">Win Rate</div>
    <div class="kpi-v" style="color:{_color(wr,.52)}">{_pct(wr)}{ci_str}</div></div>
  <div class="kpi"><div class="kpi-l">ROI Total</div>
    <div class="kpi-v" style="color:{_color(roi)}">{roi:+.2f}u</div></div>
  <div class="kpi"><div class="kpi-l">Yield</div>
    <div class="kpi-v" style="color:{_color(roi_pct)}">{roi_pct:+.1f}%</div></div>
  <div class="kpi"><div class="kpi-l">Streak</div>
    <div class="kpi-v" style="color:{_color(1 if streak_type=='WIN' else (-1 if streak_type=='LOSS' else 0))}">{'+' if streak_type=='WIN' else ('-' if streak_type=='LOSS' else '')}{streak if streak_type else '—'}</div></div>
  <div class="kpi"><div class="kpi-l">Max Drawdown</div>
    <div class="kpi-v" style="color:{dd_color}">-{max_dd:.2f}u</div></div>
  {clv_kpi}
  <div class="kpi"><div class="kpi-l">WR 7 dias</div>
    <div class="kpi-v" style="color:{_color(r7.get('win_rate',0),.52)}">{_pct(r7.get('win_rate',0))}</div></div>
  <div class="kpi"><div class="kpi-l">ROI 7 dias</div>
    <div class="kpi-v" style="color:{_color(r7.get('roi',0))}">{r7.get('roi',0):+.2f}u</div></div>"""
    else:
        pending = stats.get("pending", total)
        kpi_bar = f"""
  <div class="kpi"><div class="kpi-l">Total Picks</div><div class="kpi-v" style="color:#58a6ff">{total}</div></div>
  <div class="kpi"><div class="kpi-l">Pendentes</div><div class="kpi-v" style="color:#d29922">{pending}</div></div>
  <div class="kpi"><div class="kpi-l">Resolvidos</div><div class="kpi-v" style="color:#8b949e">0</div></div>"""

    # Breakdowns
    breakdowns_html = ""
    if resolved > 0:
        league_rows = ""
        for lg, s in stats.get("by_league", {}).items():
            if s["count"] == 0:
                continue
            reliable = s.get("reliable", True)
            row_s    = "opacity:.55;font-style:italic" if not reliable else ""
            warn     = "<span style='color:#d29922;font-size:.68rem'> ⚠</span>" if not reliable else ""
            lg_wrc   = _color(s["win_rate"], 0.52) if reliable else "#6e7681"
            lg_roic  = _color(s.get("roi", 0))     if reliable else "#6e7681"
            ci_s     = (f" <span style='font-size:.70rem;color:#6e7681'>"
                        f"[{s.get('ci_low',0):.0%}–{s.get('ci_high',1):.0%}]</span>")
            league_rows += (
                f"<tr style='{row_s}'><td>{lg}{warn}</td><td>{s['count']}</td>"
                f"<td style='color:{lg_wrc}'>{_pct(s['win_rate'])}{ci_s}</td>"
                f"<td style='color:{lg_roic}'>{s.get('roi', 0):+.2f}u</td></tr>"
            )

        breakdowns_html = (
            _table_card("Por Movimento de Odds", _breakdown_rows(stats.get("by_movement", {}))) +
            _table_card("Por Score do Sistema",  _breakdown_rows(stats.get("by_score", {}))) +
            _table_card("Por xG Total",          _breakdown_rows(stats.get("by_xg", {}))) +
            _table_card("Por Banda de Odds",     _breakdown_rows(stats.get("by_odds", {}))) +
            (f"""<div class="card"><h3>Por Liga</h3>
  <table><tr><th>Liga</th><th>Picks</th><th>WR</th><th>ROI</th></tr>{league_rows}</table>
</div>""" if league_rows else "")
        )

    # 1X2 sharp com IC
    picks_1x2 = stats.get("picks_1x2", {})
    p1x2_html = ""
    if picks_1x2.get("resolved", 0) > 0:
        ci_l     = picks_1x2.get("ci_low", 0)
        ci_h     = picks_1x2.get("ci_high", 1)
        rel_note = "" if picks_1x2.get("reliable") else "<span style='color:#d29922;font-size:.75rem'> ⚠ n&lt;20</span>"
        p1x2_html = f"""
<div class="card">
  <h3>Sharp 1X2</h3>
  <table>
    <tr><th>Picks</th><th>WR</th><th>ROI</th><th>Yield</th></tr>
    <tr>
      <td>{picks_1x2["resolved"]}{rel_note}</td>
      <td style="color:{_color(picks_1x2['win_rate'], 0.52)}">{_pct(picks_1x2['win_rate'])}
        <span style='font-size:.72rem;color:#6e7681'>[{ci_l:.0%}–{ci_h:.0%}]</span></td>
      <td style="color:{_color(picks_1x2['roi'])}">{picks_1x2['roi']:+.2f}u</td>
      <td style="color:{_color(picks_1x2['roi_pct'])}">{picks_1x2['roi_pct']:+.1f}%</td>
    </tr>
  </table>
</div>"""

    all_picks      = stats.get("all_picks_raw", [])
    picks_rows     = _picks_table(all_picks)
    pending_notice = "" if resolved > 0 else """
<div style="background:#1c2128;border:1px solid #d29922;border-radius:8px;padding:12px 16px;margin-bottom:16px;color:#d29922;font-size:.85rem;">
  ⏳ Sem resultados ainda — picks abaixo estão pendentes de resultado.
</div>"""

    script_tag = "<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'></script>" if resolved > 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Over 2.5 Scanner — Analista</title>
<meta http-equiv="refresh" content="900">
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

{clv_alert}
{pending_notice}

<div class="kpi-bar">{kpi_bar}</div>

{charts_html}
{breakdowns_html}

<div class="card">
  <h3>Picks Recentes</h3>
  <table>
    <tr><th>Jogo</th><th>Mov.</th><th>Score</th><th>Odds</th><th>xG</th><th>Sharp</th><th>Result.</th></tr>
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
