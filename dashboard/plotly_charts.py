# dashboard/plotly_charts.py — Gráficos Plotly interativos para o sistema Analista
import json
from datetime import datetime

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import numpy as np
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False
    go = None

# ── Paleta dark ───────────────────────────────────────────────────────────────
_BG      = "#0d0d0b"
_SURFACE = "#131311"
_BORDER  = "#232322"
_TEXT    = "#c8c4be"
_MUTED   = "#7a7670"
_GREEN   = "#40b89a"
_GOLD    = "#c9a030"
_RED     = "#c04539"
_BLUE    = "#6a90c4"

_LAYOUT_BASE = dict(
    paper_bgcolor=_BG,
    plot_bgcolor=_BG,
    font=dict(color=_TEXT, family="Albert Sans, Helvetica Neue, Arial, sans-serif", size=12),
    margin=dict(l=48, r=24, t=36, b=36),
    xaxis=dict(gridcolor=_BORDER, tickcolor=_MUTED, linecolor=_BORDER, zerolinecolor=_BORDER),
    yaxis=dict(gridcolor=_BORDER, tickcolor=_MUTED, linecolor=_BORDER, zerolinecolor=_BORDER),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=_BORDER, font=dict(color=_TEXT)),
)


def _base_fig(**extra):
    if not _PLOTLY_OK:
        return None
    fig = go.Figure()
    layout = {**_LAYOUT_BASE, **extra}
    fig.update_layout(**layout)
    return fig


def roi_cumulative_chart(over25_stats) -> "go.Figure | None":
    """Linha de ROI acumulado: All picks + SHORTENING + DRIFTING."""
    if not _PLOTLY_OK:
        return None

    cum_all  = over25_stats.get("cumulative_roi", [])
    by_mov   = over25_stats.get("by_movement", {})

    fig = _base_fig(title=dict(text="ROI Acumulado — Over 2.5", font=dict(color=_GOLD, size=14)))

    if cum_all:
        x = list(range(1, len(cum_all) + 1))
        fig.add_trace(go.Scatter(
            x=x, y=cum_all, mode="lines", name="Todos",
            line=dict(color=_GREEN, width=2),
            fill="tozeroy", fillcolor="rgba(64,184,154,0.07)",
        ))
        fig.add_hline(y=0, line=dict(color=_BORDER, dash="dash", width=1))

    # Linhas por movimento (recalculadas a partir dos picks raw se disponível)
    fig.update_layout(
        yaxis_title="ROI (u)",
        xaxis_title="Pick #",
        hovermode="x unified",
    )
    return fig


def rolling_wr_chart(over25_stats) -> "go.Figure | None":
    """Win rate rolling 20 + banda de confiança + linha break-even."""
    if not _PLOTLY_OK:
        return None

    rolling = over25_stats.get("rolling_wr_series", [])
    if not rolling:
        return None

    x = list(range(1, len(rolling) + 1))
    # Banda approx ± 1 std de uma binomial com p=wr, n=20
    wr   = over25_stats.get("win_rate", 0.5)
    std  = (wr * (1 - wr) / 20) ** 0.5
    upper = [min(1.0, v + 1.96 * std) for v in rolling]
    lower = [max(0.0, v - 1.96 * std) for v in rolling]

    fig = _base_fig(title=dict(text="Win Rate Rolling (20 picks)", font=dict(color=_GOLD, size=14)))

    fig.add_trace(go.Scatter(
        x=x + x[::-1], y=upper + lower[::-1],
        fill="toself", fillcolor="rgba(106,144,196,0.10)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False, name="IC 95%",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=rolling, mode="lines", name="WR Rolling",
        line=dict(color=_BLUE, width=2),
    ))
    fig.add_hline(y=0.526, line=dict(color=_RED, dash="dot", width=1.5),
                  annotation_text="Break-even O2.5", annotation_font_color=_RED)
    fig.add_hline(y=wr, line=dict(color=_MUTED, dash="dash", width=1),
                  annotation_text=f"WR global {wr:.1%}", annotation_font_color=_MUTED)

    fig.update_layout(yaxis_title="Win Rate", xaxis_title="Pick #",
                      yaxis=dict(tickformat=".0%", **_LAYOUT_BASE["yaxis"]))
    return fig


def calibration_chart(football_stats) -> "go.Figure | None":
    """Reliability diagram: prob prevista vs frequência real."""
    if not _PLOTLY_OK:
        return None

    cal = football_stats.get("calibration", {})
    if not cal:
        return None

    fig = _base_fig(title=dict(text="Calibração do Modelo (Reliability Diagram)", font=dict(color=_GOLD, size=14)))

    # Linha perfeita
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="Calibração perfeita",
        line=dict(color=_MUTED, dash="dash", width=1),
    ))

    colors = {"o25": _GREEN, "btts": _BLUE}
    names  = {"o25": "Over 2.5", "btts": "BTTS"}
    for key, col in colors.items():
        data = cal.get(key, [])
        xs = [d["predicted"] for d in data if d.get("actual") is not None and d.get("n", 0) >= 3]
        ys = [d["actual"]    for d in data if d.get("actual") is not None and d.get("n", 0) >= 3]
        ns = [d["n"]         for d in data if d.get("actual") is not None and d.get("n", 0) >= 3]
        if xs:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="markers+lines", name=names[key],
                marker=dict(color=col, size=[max(6, min(20, n//3)) for n in ns],
                            line=dict(color=_BG, width=1)),
                line=dict(color=col, width=1.5),
            ))

    fig.update_layout(
        xaxis_title="Probabilidade Prevista",
        yaxis_title="Frequência Real",
        xaxis=dict(tickformat=".0%", range=[0, 1], **_LAYOUT_BASE["xaxis"]),
        yaxis=dict(tickformat=".0%", range=[0, 1], **_LAYOUT_BASE["yaxis"]),
    )
    return fig


def market_comparison_bar(football_stats) -> "go.Figure | None":
    """Barras agrupadas: WR e ROI por mercado."""
    if not _PLOTLY_OK:
        return None

    pm = football_stats.get("per_market", {})
    markets = ["o25", "btts", "1x2"]
    labels  = ["Over 2.5", "BTTS", "1X2"]
    wr_vals = [pm.get(m, {}).get("win_rate", 0) * 100 for m in markets]
    roi_vals = [pm.get(m, {}).get("roi", 0) for m in markets]

    fig = _base_fig(title=dict(text="Comparação por Mercado", font=dict(color=_GOLD, size=14)))
    fig.add_trace(go.Bar(name="Win Rate (%)", x=labels, y=wr_vals,
                         marker_color=_BLUE, yaxis="y"))
    fig.add_trace(go.Bar(name="ROI (u)", x=labels, y=roi_vals,
                         marker_color=[_GREEN if v >= 0 else _RED for v in roi_vals], yaxis="y2"))

    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Win Rate (%)", **_LAYOUT_BASE["yaxis"]),
        yaxis2=dict(title="ROI (u)", overlaying="y", side="right",
                    gridcolor=_BORDER, tickcolor=_MUTED, linecolor=_BORDER),
        legend=dict(**_LAYOUT_BASE["legend"]),
    )
    # Break-even lines per market
    break_evens = {"Over 2.5": 52.6, "BTTS": 54.1, "1X2": 45.5}
    for label, be in break_evens.items():
        fig.add_hline(y=be, line=dict(color=_MUTED, dash="dot", width=0.8))
    return fig


def elo_ratings_chart(elo_ratings) -> "go.Figure | None":
    """Barras horizontais com top 20 ratings Elo."""
    if not _PLOTLY_OK:
        return None
    if not elo_ratings:
        return None

    top = elo_ratings[:20]
    teams   = [t[0] for t in reversed(top)]
    ratings = [t[1] for t in reversed(top)]
    colors  = [_GREEN if r >= 1500 else (_GOLD if r >= 1400 else _MUTED) for r in ratings]

    fig = _base_fig(title=dict(text="Top 20 Ratings Elo", font=dict(color=_GOLD, size=14)))
    fig.add_trace(go.Bar(
        x=ratings, y=teams, orientation="h",
        marker_color=colors, text=[f"{r:.0f}" for r in ratings],
        textposition="outside", textfont=dict(color=_TEXT, size=11),
    ))
    fig.add_vline(x=1500, line=dict(color=_MUTED, dash="dash", width=1))
    fig.update_layout(
        xaxis=dict(title="Rating Elo", range=[1200, max(ratings) + 100] if ratings else [1200, 1800],
                   **_LAYOUT_BASE["xaxis"]),
        margin=dict(l=160, r=60, t=36, b=36),
        height=max(300, len(top) * 28),
    )
    return fig


def heatmap_daily_roi(over25_stats) -> "go.Figure | None":
    """Heatmap de ROI diário (mês × dia do mês)."""
    if not _PLOTLY_OK:
        return None

    daily = over25_stats.get("daily", {})
    if not daily:
        return None

    # Organizar em matriz mês × dia
    from collections import defaultdict
    months = sorted({d[:7] for d in daily.keys()})
    max_day = 31
    matrix  = [[None] * max_day for _ in months]
    month_idx = {m: i for i, m in enumerate(months)}

    for date_str, day_data in daily.items():
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            mi = month_idx.get(date_str[:7])
            if mi is not None:
                matrix[mi][dt.day - 1] = round(day_data.get("roi", 0), 2)
        except ValueError:
            pass

    z_vals = [[v if v is not None else 0 for v in row] for row in matrix]
    text   = [[f"{v:+.2f}u" if v is not None else "" for v in row] for row in matrix]

    fig = _base_fig(title=dict(text="ROI Diário — Heatmap", font=dict(color=_GOLD, size=14)))
    fig.add_trace(go.Heatmap(
        z=z_vals, x=list(range(1, max_day + 1)), y=months,
        text=text, texttemplate="%{text}", textfont=dict(size=9),
        colorscale=[[0, _RED], [0.5, _SURFACE], [1, _GREEN]],
        zmid=0, showscale=True,
        colorbar=dict(tickfont=dict(color=_TEXT), outlinecolor=_BORDER),
    ))
    fig.update_layout(
        xaxis_title="Dia do Mês",
        height=max(200, len(months) * 40 + 80),
    )
    return fig


def scatter_xg_vs_result(picks) -> "go.Figure | None":
    """Scatter: xG total vs odds, colorido por resultado."""
    if not _PLOTLY_OK:
        return None
    if not picks:
        return None

    color_map  = {"WIN": _GREEN, "LOSS": _RED, None: _MUTED, "": _MUTED}
    symbol_map = {"WIN": "circle", "LOSS": "x", None: "circle-open", "": "circle-open"}

    xs, ys, colors_pt, symbols_pt, texts = [], [], [], [], []
    for p in picks:
        try:
            xg   = float(p.get("xg_total") or 0)
            odds = float(p.get("odds_over") or 0)
            res  = p.get("result_over25") or None
            if xg <= 0 or odds <= 1:
                continue
            xs.append(xg)
            ys.append(odds)
            colors_pt.append(color_map.get(res, _MUTED))
            symbols_pt.append(symbol_map.get(res, "circle-open"))
            texts.append(f"{p.get('casa','?')} vs {p.get('fora','?')}<br>xG={xg:.1f} | Odds={odds:.2f} | {res or 'pendente'}")
        except (TypeError, ValueError):
            pass

    if not xs:
        return None

    fig = _base_fig(title=dict(text="xG vs Odds — Por Resultado", font=dict(color=_GOLD, size=14)))
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", text=texts,
        hoverinfo="text",
        marker=dict(color=colors_pt, symbol=symbols_pt, size=8,
                    line=dict(color=_BG, width=0.5)),
        showlegend=False,
    ))
    # Legenda manual
    for res, col, sym, label in [("WIN", _GREEN, "circle", "WIN"), ("LOSS", _RED, "x", "LOSS"), (None, _MUTED, "circle-open", "Pendente")]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(color=col, symbol=sym, size=8),
            name=label, showlegend=True,
        ))
    fig.add_hline(y=1.90, line=dict(color=_MUTED, dash="dash", width=0.8),
                  annotation_text="Odds base O2.5", annotation_font_color=_MUTED)

    fig.update_layout(
        xaxis_title="xG Total Previsto",
        yaxis_title="Odds Over 2.5",
    )
    return fig


def to_html(fig) -> str:
    """Converte figura Plotly para div HTML (sem JS Plotly)."""
    if not _PLOTLY_OK or fig is None:
        return "<div style='color:#7a7670;text-align:center;padding:20px'>Gráfico indisponível (plotly não instalado)</div>"
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})


def to_standalone_html(fig, title="Gráfico") -> str:
    """HTML completo com CDN Plotly."""
    if not _PLOTLY_OK or fig is None:
        return f"<html><body><p>Plotly não disponível</p></body></html>"
    return fig.to_html(full_html=True, include_plotlyjs="cdn",
                       config={"displayModeBar": False})
