# dashboard/gen_advanced.py — Dashboard avançado com gráficos Plotly interativos
import os
from utils import DOCS_DIR, pct, color, now_lisbon

try:
    from dashboard.plotly_charts import (
        roi_cumulative_chart, rolling_wr_chart, calibration_chart,
        market_comparison_bar, scatter_xg_vs_result, heatmap_daily_roi, to_html,
        _PLOTLY_OK,
    )
except ImportError:
    _PLOTLY_OK = False
    def to_html(_): return "<div style='color:#7a7670;text-align:center;padding:20px'>Plotly não disponível</div>"


_CDN_PLOTLY = "https://cdn.plot.ly/plotly-2.27.0.min.js"
_GOLD       = "oklch(84% 0.19 80.46)"
_PATINA     = "oklch(70% 0.12 188)"
_VERMILION  = "oklch(58% 0.15 35)"
_LACQUER    = "oklch(7% 0.006 95)"
_RAISED     = "oklch(11% 0.006 95)"
_MUTED      = "oklch(63% 0.024 82)"
_BORDER     = "oklch(28% 0.010 95)"


def _kpi(label, value, color_css=_PATINA):
    return (f"<div style='background:{_RAISED};border:1px solid {_BORDER};border-radius:2px;"
            f"padding:14px 18px;min-width:130px'>"
            f"<div style='font-size:.70rem;color:{_MUTED};text-transform:uppercase;letter-spacing:.05em'>{label}</div>"
            f"<div style='font-size:1.35rem;font-weight:700;margin-top:4px;color:{color_css}'>{value}</div>"
            f"</div>")


def _section(title, content):
    return (f"<div style='background:{_RAISED};border:1px solid {_BORDER};border-radius:2px;"
            f"padding:20px;margin-bottom:20px'>"
            f"<h3 style='font-size:.78rem;color:{_MUTED};text-transform:uppercase;letter-spacing:.05em;"
            f"margin-bottom:16px'>{title}</h3>"
            f"{content}</div>")


def gen_advanced_dashboard(over25_stats, football_stats, picks_raw=None, elo_system=None) -> str:
    """
    Gera HTML completo com múltiplos gráficos Plotly interativos.
    Integra métricas do Over 2.5 Scanner e Matemática Da Bola.
    """
    now  = now_lisbon().strftime("%d/%m/%Y %H:%M Lisboa")
    o25  = over25_stats
    fb   = football_stats
    pm   = fb.get("per_market", {})

    # ── KPIs ─────────────────────────────────────────────────────────────────
    wr       = o25.get("win_rate", 0)
    roi      = o25.get("roi", 0)
    dd       = o25.get("max_drawdown", 0)
    clv      = o25.get("avg_clv")
    resolved = o25.get("resolved", 0)
    pending  = o25.get("pending", 0)

    wr_c  = _PATINA  if wr >= 0.526   else _VERMILION
    roi_c = _PATINA  if roi >= 0      else _VERMILION
    dd_c  = _GOLD    if dd < 5        else _VERMILION
    clv_c = _PATINA  if (clv or 0) >= 0 else _VERMILION
    clv_s = f"{clv:+.2f}%" if clv is not None else "N/D"

    kpis_html = "".join([
        _kpi("O2.5 Win Rate",  pct(wr),              wr_c),
        _kpi("ROI Acumulado",  f"{roi:+.2f}u",        roi_c),
        _kpi("Max Drawdown",   f"-{dd:.2f}u",          dd_c),
        _kpi("CLV Médio",      clv_s,                 clv_c),
        _kpi("Picks Resolvidas", str(resolved),       _MUTED),
        _kpi("Football O2.5 WR", pct(pm.get("o25",{}).get("win_rate",0)),
             _PATINA if pm.get("o25",{}).get("win_rate",0) >= 0.60 else _VERMILION),
        _kpi("Football BTTS WR", pct(pm.get("btts",{}).get("win_rate",0)),
             _PATINA if pm.get("btts",{}).get("win_rate",0) >= 0.60 else _VERMILION),
    ])

    # ── Gráficos Plotly ───────────────────────────────────────────────────────
    charts = []

    if _PLOTLY_OK:
        fig_roi  = roi_cumulative_chart(o25)
        fig_rwr  = rolling_wr_chart(o25)
        fig_cal  = calibration_chart(fb)
        fig_mkt  = market_comparison_bar(fb)
        fig_scat = scatter_xg_vs_result(picks_raw or []) if picks_raw else None
        fig_heat = heatmap_daily_roi(o25)

        chart_pairs = [
            ("ROI Acumulado — Over 2.5 Scanner", fig_roi),
            ("Win Rate Rolling (20 picks)", fig_rwr),
            ("Calibração do Modelo", fig_cal),
            ("Comparação de Mercados", fig_mkt),
        ]
        if fig_scat:
            chart_pairs.append(("xG vs Odds (scatter)", fig_scat))
        if fig_heat:
            chart_pairs.append(("ROI Diário — Heatmap", fig_heat))

        for i in range(0, len(chart_pairs), 2):
            pair = chart_pairs[i:i+2]
            cols = "".join(
                f"<div style='flex:1;min-width:0'>"
                f"<div style='font-size:.70rem;color:{_MUTED};text-transform:uppercase;"
                f"letter-spacing:.04em;margin-bottom:8px'>{title}</div>"
                f"{to_html(fig)}</div>"
                for title, fig in pair
            )
            charts.append(
                f"<div style='display:flex;gap:20px;margin-bottom:20px'>{cols}</div>"
            )
    else:
        charts.append(
            f"<div style='color:{_MUTED};text-align:center;padding:40px'>"
            f"Instalar plotly para gráficos interativos: <code>pip install plotly</code></div>"
        )

    charts_html = "\n".join(charts)

    # ── Alertas do monitor ────────────────────────────────────────────────────
    alerts_html = ""
    try:
        from data_quality.monitor import run_all_checks
        monitor = run_all_checks(o25, fb)
        alerts  = monitor.get("alerts", [])
        health  = monitor.get("overall_health", "healthy")
        health_color = {
            "healthy":  _PATINA,
            "warning":  _GOLD,
            "critical": _VERMILION,
        }.get(health, _MUTED)

        if alerts:
            items = "".join(
                f"<li style='margin-bottom:6px;color:{_GOLD if '⚠️' in a else _VERMILION if '🔴' in a else _PATINA}'>{a}</li>"
                for a in alerts
            )
            alerts_html = _section(
                f"🔍 Monitor de Qualidade — <span style='color:{health_color}'>{health.upper()}</span>",
                f"<ul style='padding-left:18px;font-size:.83rem'>{items}</ul>"
            )
    except Exception:
        pass

    # ── Brier Scores ──────────────────────────────────────────────────────────
    bs = fb.get("brier_scores", {})
    bs_html = ""
    if bs:
        def _interp(v):
            if v is None:
                return "N/D"
            return ("✅ Excelente" if v < 0.15 else
                    "✅ Bom"       if v < 0.20 else
                    "⚠️ Aceitável" if v < 0.25 else "❌ Fraco")
        items = ""
        for k, v in bs.items():
            v_str = f"{v:.4f}" if v is not None else "N/D"
            items += (
                f"<div style='display:flex;justify-content:space-between;padding:6px 0;"
                f"border-bottom:1px solid {_BORDER}'>"
                f"<span style='color:{_MUTED}'>{k.upper()}</span>"
                f"<span>{v_str} — {_interp(v)}</span></div>"
            )
        bs_html = _section("Brier Scores (calibração do modelo)", items)

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analista — Analytics Avançados</title>
<meta http-equiv="refresh" content="1800">
<script src="{_CDN_PLOTLY}"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Albert+Sans:wght@300;400;500;600&family=Alumni+Sans+Pinstripe&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{_LACQUER};color:oklch(81% 0.03 82);font-family:"Albert Sans","Helvetica Neue",Arial,system-ui,sans-serif;padding:24px;font-size:14px}}
h1{{font-size:1.5rem;color:{_GOLD};margin-bottom:4px;font-family:"Alumni Sans Pinstripe","Albert Sans",sans-serif;font-weight:300;letter-spacing:.02em}}
.sub{{color:{_MUTED};font-size:.72rem;font-family:"SFMono-Regular",Consolas,monospace;text-transform:uppercase;letter-spacing:.04em;margin-bottom:22px}}
.kpi-bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}}
code{{background:{_RAISED};padding:2px 6px;border-radius:2px;font-size:.82em;color:{_GOLD}}}
@media(max-width:700px){{body{{padding:14px}}}}
</style>
</head>
<body>
<h1>📈 Analista — Analytics Avançados</h1>
<p class="sub">Actualizado: {now} · Plotly interativo · Over 2.5 Scanner + Matemática Da Bola</p>

<div class="kpi-bar">{kpis_html}</div>

{alerts_html}

{_section("Gráficos Interativos", charts_html)}

{bs_html}

<p style='text-align:center;color:{_MUTED};font-size:.72rem;margin-top:20px'>
  Analista · Analytics Avançados · nunovinhas-creator/Analista
</p>
</body>
</html>"""


def save_advanced_dashboard(over25_stats, football_stats, picks_raw=None):
    """Gera e guarda docs/advanced_dashboard.html."""
    os.makedirs(DOCS_DIR, exist_ok=True)
    html = gen_advanced_dashboard(over25_stats, football_stats, picks_raw=picks_raw)
    path = os.path.join(DOCS_DIR, "advanced_dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[dashboard] advanced_dashboard.html gerado")
