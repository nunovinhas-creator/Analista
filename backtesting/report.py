# backtesting/report.py — Gerador de relatório HTML para backtesting
import json
import os
from datetime import datetime, timezone

_HERE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPORTS = os.path.join(_HERE, "docs")

_DARK = {
    "bg":      "#0d0d0b",
    "surface": "#131311",
    "border":  "#232322",
    "text":    "#c8c4be",
    "muted":   "#7a7670",
    "green":   "#40b89a",
    "gold":    "#c9a030",
    "red":     "#c04539",
    "blue":    "#6a90c4",
}


def _color(v):
    return _DARK["green"] if v >= 0 else _DARK["red"]


def _pct(v, d=1):
    return f"{v*100:.{d}f}%" if v is not None else "—"


def _fmt(v, fmt="+.2f"):
    try:
        return format(v, fmt)
    except Exception:
        return "—"


def generate_report(results: dict, title="Relatório de Backtesting") -> str:
    """
    Gera HTML completo comparando múltiplas estratégias de backtesting.
    results: dict mapping strategy_name -> BacktestResult
    """
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    # ── Tabela de resumo ──────────────────────────────────────────────────────
    header_cols = ["Estratégia", "Saldo Final", "ROI (u)", "Yield", "WR", "Max DD", "Bets", "Sharpe"]
    rows_html = ""
    for name, r in results.items():
        bal_c  = _color(r.final_balance - 100)
        roi_c  = _color(r.roi)
        dd_c   = _DARK["gold"] if r.max_drawdown < 5 else _DARK["red"]
        rows_html += f"""
<tr>
  <td style='padding:8px 12px;font-weight:600'>{name}</td>
  <td style='padding:8px 12px;color:{bal_c}'>{r.final_balance:.2f}u</td>
  <td style='padding:8px 12px;color:{roi_c}'>{r.roi:+.2f}u</td>
  <td style='padding:8px 12px;color:{roi_c}'>{r.roi_pct:+.1f}%</td>
  <td style='padding:8px 12px;color:{_color(r.win_rate - 0.52)}'>{_pct(r.win_rate)}</td>
  <td style='padding:8px 12px;color:{dd_c}'>{r.max_drawdown:.2f}u</td>
  <td style='padding:8px 12px;color:{_DARK["muted"]}'>{r.n_bets}</td>
  <td style='padding:8px 12px;color:{_color(r.sharpe)}'>{r.sharpe:+.2f}</td>
</tr>"""

    th_s = f"padding:8px 12px;text-align:left;border-bottom:1px solid {_DARK['border']};color:{_DARK['muted']};font-size:.78rem;text-transform:uppercase;letter-spacing:.04em"
    header_html = "".join(f"<th style='{th_s}'>{c}</th>" for c in header_cols)

    # ── Dados para Chart.js (bankroll evolution) ──────────────────────────────
    chart_datasets = []
    colors = [_DARK["green"], _DARK["gold"], _DARK["blue"], _DARK["red"],
              "#a06090", "#6090a0", "#90a060", "#c08040"]
    max_len = max((len(r.bankroll_history) for r in results.values()), default=0)
    labels  = json.dumps(list(range(1, max_len + 1)))

    for i, (name, r) in enumerate(results.items()):
        col = colors[i % len(colors)]
        chart_datasets.append({
            "label":           name,
            "data":            r.bankroll_history,
            "borderColor":     col,
            "backgroundColor": col.replace("#", "rgba(") + ",0)",
            "fill":            False,
            "tension":         0.1,
            "pointRadius":     0,
            "borderWidth":     2,
        })
    datasets_json = json.dumps(chart_datasets)

    # ── Por mercado (melhor estratégia) ───────────────────────────────────────
    best_r   = next(iter(results.values())) if results else None
    mkt_rows = ""
    if best_r:
        for mkt, s in best_r.by_market.items():
            if not s.get("n"):
                continue
            c = _color(s.get("roi", 0))
            mkt_rows += f"<tr><td style='padding:6px 10px'>{mkt.upper()}</td><td style='padding:6px 10px;color:{_DARK['muted']}'>{s['n']}</td><td style='padding:6px 10px;color:{_color(s['win_rate']-0.52)}'>{_pct(s['win_rate'])}</td><td style='padding:6px 10px;color:{c}'>{s.get('roi',0):+.2f}u</td></tr>"

    # ── Por mês (melhor estratégia) ───────────────────────────────────────────
    month_rows = ""
    if best_r:
        for month in sorted(best_r.by_month.keys()):
            ms  = best_r.by_month[month]
            c   = _color(ms.get("roi", 0))
            month_rows += f"<tr><td style='padding:6px 10px'>{month}</td><td style='padding:6px 10px;color:{_DARK['muted']}'>{ms.get('n',0)}</td><td style='padding:6px 10px;color:{c}'>{ms.get('roi',0):+.2f}u</td><td style='padding:6px 10px;color:{_color(ms.get('win_rate',0)-0.52)}'>{_pct(ms.get('win_rate',0))}</td></tr>"

    # ── Top ligas ─────────────────────────────────────────────────────────────
    league_rows = ""
    if best_r:
        top_leagues = sorted(best_r.by_league.items(),
                             key=lambda x: abs(x[1].get("roi", 0)), reverse=True)[:10]
        for lg, ls in top_leagues:
            c    = _color(ls.get("roi", 0))
            wr_c = _color(ls.get("win_rate", 0) - 0.52)
            league_rows += (
                f"<tr><td style='padding:6px 10px'>{lg}</td>"
                f"<td style='padding:6px 10px;color:{_DARK['muted']}'>{ls.get('n',0)}</td>"
                f"<td style='padding:6px 10px;color:{wr_c}'>{_pct(ls.get('win_rate',0))}</td>"
                f"<td style='padding:6px 10px;color:{c}'>{ls.get('roi',0):+.2f}u</td></tr>"
            )

    td_s  = f"border-bottom:1px solid {_DARK['border']}"
    th_s2 = f"padding:6px 10px;text-align:left;border-bottom:1px solid {_DARK['border']};color:{_DARK['muted']};font-size:.75rem"

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{_DARK['bg']};color:{_DARK['text']};font-family:"Albert Sans","Helvetica Neue",Arial,sans-serif;padding:24px;font-size:14px}}
h1{{font-size:1.4rem;color:{_DARK['gold']};margin-bottom:4px}}
h2{{font-size:.85rem;color:{_DARK['muted']};text-transform:uppercase;letter-spacing:.06em;margin:28px 0 12px}}
.card{{background:{_DARK['surface']};border:1px solid {_DARK['border']};border-radius:2px;padding:20px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;border-bottom:1px solid {_DARK['border']};color:{_DARK['muted']};font-size:.75rem;padding:8px 12px;text-transform:uppercase;letter-spacing:.04em}}
td{{border-bottom:1px solid {_DARK['border']};vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
.sub{{color:{_DARK['muted']};font-size:.78rem;font-family:monospace;text-transform:uppercase;letter-spacing:.04em}}
</style>
</head>
<body>
<h1>📊 {title}</h1>
<p class="sub" style="margin-bottom:24px">Gerado: {now}</p>

<div class="card">
<h2>Comparação de Estratégias</h2>
<div style="overflow-x:auto">
<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>
</div>
</div>

<div class="card">
<h2>Evolução do Bankroll</h2>
<canvas id="bankrollChart" height="100"></canvas>
<script>
(function(){{
  var ctx = document.getElementById('bankrollChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{ labels: {labels}, datasets: {datasets_json} }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ labels: {{ color: '{_DARK['text']}' }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '{_DARK['muted']}', maxTicksLimit: 15 }}, grid: {{ color: '{_DARK['border']}' }} }},
        y: {{ ticks: {{ color: '{_DARK['muted']}' }}, grid: {{ color: '{_DARK['border']}' }} }}
      }}
    }}
  }});
}})();
</script>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px">
<div class="card">
<h2>Por Mercado</h2>
<table><thead><tr>
  <th style="{th_s2}">Mercado</th><th style="{th_s2}">Bets</th>
  <th style="{th_s2}">WR</th><th style="{th_s2}">ROI</th>
</tr></thead><tbody>{mkt_rows}</tbody></table>
</div>
<div class="card">
<h2>Por Mês</h2>
<table><thead><tr>
  <th style="{th_s2}">Mês</th><th style="{th_s2}">Bets</th>
  <th style="{th_s2}">ROI</th><th style="{th_s2}">WR</th>
</tr></thead><tbody>{month_rows}</tbody></table>
</div>
<div class="card">
<h2>Top Ligas</h2>
<table><thead><tr>
  <th style="{th_s2}">Liga</th><th style="{th_s2}">Bets</th>
  <th style="{th_s2}">WR</th><th style="{th_s2}">ROI</th>
</tr></thead><tbody>{league_rows}</tbody></table>
</div>
</div>

<p style="text-align:center;color:{_DARK['muted']};font-size:.72rem;margin-top:20px">
  Analista · Backtesting Determinístico · nunovinhas-creator/Analista
</p>
</body>
</html>"""


def save_report(results, path=None):
    """Guarda relatório HTML em docs/backtest_report.html."""
    path = path or os.path.join(_REPORTS, "backtest_report.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    html = generate_report(results)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[backtest] relatório guardado em {path}")


def backtest_summary_stats(result) -> dict:
    """Dicionário de resumo para uso noutros dashboards."""
    return {
        "roi":          result.roi,
        "roi_pct":      result.roi_pct,
        "win_rate":     result.win_rate,
        "max_drawdown": result.max_drawdown,
        "n_bets":       result.n_bets,
        "final_balance": result.final_balance,
        "sharpe":       result.sharpe,
        "by_market":    result.by_market,
    }


def print_summary(result):
    """Imprime resumo de backtesting no stdout."""
    print(f"  Bets:     {result.n_bets}")
    print(f"  Win Rate: {result.win_rate:.1%}")
    print(f"  ROI:      {result.roi:+.2f}u  ({result.roi_pct:+.1f}%/bet)")
    print(f"  Max DD:   {result.max_drawdown:.2f}u")
    print(f"  Sharpe:   {result.sharpe:+.2f}")
    print(f"  Balance:  {result.final_balance:.2f}u  (start 100u)")
