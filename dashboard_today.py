# dashboard_today.py — Gera docs/today_dashboard.html ("Onde Apostar Hoje")
import json
import os
from datetime import datetime, timedelta, timezone
from utils import DOCS_DIR, pct, color, escape, MARKET_BASE_ODDS, MARKET_LABELS


def _edge_badge(edge):
    if edge == "strong":
        return "<span class='edge-badge edge-strong'>✅ Forte</span>"
    if edge == "moderate":
        return "<span class='edge-badge edge-moderate'>⚠️ Moderado</span>"
    if edge == "weak":
        return "<span class='edge-badge edge-weak'>❌ Fraco</span>"
    return "<span class='edge-badge edge-insuf'>📊 Dados insuf.</span>"


def _conf_badge(conf):
    s = _CONF_STYLES.get(conf, _CONF_STYLE_DEFAULT)
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
        "strong":      "oklch(70% 0.12 188 / 0.5)",
        "moderate":    "oklch(84% 0.19 80.46 / 0.45)",
        "weak":        "oklch(28% 0.010 95)",
        "insufficient": "oklch(28% 0.010 95)",
    }.get(edge, "oklch(28% 0.010 95)")
    bg_color = {
        "strong":  "oklch(11% 0.006 95)",
        "moderate": "oklch(11% 0.006 95)",
    }.get(edge, "oklch(11% 0.006 95)")

    dir_label = _dir_label(pick.get("dir"))
    market_title = f"{label}" + (f" <span style='font-size:.78rem;color:oklch(63% 0.024 82)'>({dir_label})</span>" if dir_label else "")

    # Stats line (ref)
    warn_n = "" if pick["ref_reliable"] else " <span style='color:oklch(48% 0.12 80);font-size:.72rem'>⚠ n&lt;20</span>"
    ref_src_label = ref_label if ref_label in ("ALTA", "MÉDIA", "BAIXA") else "global"
    ref_line = (f"<div class='stat-line'>"
                f"<span class='stat-key'>Backtest {ref_src_label}:</span>"
                f" <b style='color:{color(ref_wr, 1/odds)}'>{pct(ref_wr)}</b>"
                f" (n={ref_n})"
                f" <span style='color:oklch(55% 0.014 82)'>[{ref_ci_l:.0%}–{ref_ci_h:.0%}]</span>"
                f"{warn_n}</div>")

    # Global line (only if different from ref)
    global_line = ""
    if ref_label not in ("global",) and global_n >= 5:
        global_line = (f"<div class='stat-line'>"
                       f"<span class='stat-key'>Backtest global:</span>"
                       f" {pct(global_wr)} (n={global_n})"
                       f"</div>")

    # League line
    league_line = ""
    if league_n >= 5:
        league_warn = " <span style='color:oklch(48% 0.12 80);font-size:.72rem'>⚠ n&lt;10</span>" if league_n < 10 else ""
        league_ci   = f" <span style='color:oklch(55% 0.014 82)'>[{pick['league_ci_l']:.0%}–{pick['league_ci_h']:.0%}]</span>" if league_n >= 5 else ""
        league_line = (f"<div class='stat-line'>"
                       f"<span class='stat-key'>Liga:</span>"
                       f" <b style='color:{color(league_wr, 1/odds)}'>{pct(league_wr)}</b>"
                       f" (n={league_n}){league_ci}{league_warn}</div>")

    # Kelly line
    kelly_line = ""
    if edge in ("strong", "moderate") and kq > 0:
        kelly_color = "oklch(70% 0.12 188)" if edge == "strong" else "oklch(84% 0.19 80.46)"
        kelly_line  = (f"<div class='stat-line kelly-line'>"
                       f"<span class='stat-key'>Kelly ¼:</span>"
                       f" <b style='color:{kelly_color}'>{kq:.1f}% da banca</b>"
                       f" <span style='color:oklch(55% 0.014 82)'>(odds base {odds:.2f}x)</span>"
                       f"</div>")
    elif edge == "weak":
        kelly_line = "<div class='stat-line'><span style='color:oklch(55% 0.014 82);font-size:.78rem'>EV negativo — sem recomendação de stake</span></div>"
    else:
        kelly_line = "<div class='stat-line'><span style='color:oklch(55% 0.014 82);font-size:.78rem'>Dados insuficientes — sem recomendação</span></div>"

    return f"""
<div class='pick-block' style='background:{bg_color};border:1px solid {border_color};border-radius:2px;padding:12px 14px;margin-bottom:8px'>
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

_CONF_STYLES = {
    "ALTA":  "background:oklch(11% 0.006 95);color:oklch(70% 0.12 188);border:1px solid oklch(70% 0.12 188 / 0.45)",
    "MÉDIA": "background:oklch(11% 0.006 95);color:oklch(84% 0.19 80.46);border:1px solid oklch(84% 0.19 80.46 / 0.45)",
    "BAIXA": "background:oklch(11% 0.006 95);color:oklch(58% 0.15 35);border:1px solid oklch(58% 0.15 35 / 0.45)",
}
_CONF_STYLE_DEFAULT = "background:oklch(11% 0.006 95);color:oklch(63% 0.024 82);border:1px solid oklch(28% 0.010 95)"


def _tracker_section(perf):
    n       = perf["total_resolved"]
    pending = perf["total_pending"]

    if n == 0:
        return (
            f"<div class='card'>"
            f"<h3>Performance do Analista — Backtest Próprio</h3>"
            f"<div style='text-align:center;padding:24px;color:oklch(63% 0.024 82)'>"
            f"<div style='font-size:1.8rem;margin-bottom:10px'>📊</div>"
            f"<div style='color:oklch(84% 0.035 82)'>A acumular dados — {pending} pick{'s' if pending != 1 else ''} pendente{'s' if pending != 1 else ''} de resolução</div>"
            f"<div style='font-size:.78rem;margin-top:8px'>As picks identificadas hoje são registadas e comparadas com os resultados reais assim que ficarem disponíveis.</div>"
            f"</div></div>"
        )

    wr      = perf["win_rate"]
    roi     = perf["roi"]
    roi_pct = perf["roi_pct"]
    wins    = perf["wins"]
    losses  = perf["losses"]
    wr_c    = "oklch(70% 0.12 188)" if wr >= 0.50 else "oklch(58% 0.15 35)"
    roi_c   = "oklch(70% 0.12 188)" if roi >= 0   else "oklch(58% 0.15 35)"

    TS  = "width:100%;border-collapse:collapse;font-size:.82rem"
    TH  = "text-align:left;color:oklch(55% 0.014 82);padding:4px 8px;border-bottom:1px solid oklch(15% 0.008 95);font-weight:500"
    TD  = "padding:4px 8px;border-bottom:1px solid oklch(15% 0.008 95)"
    TDN = "padding:4px 8px;border-bottom:1px solid oklch(15% 0.008 95);color:oklch(63% 0.024 82)"

    # -- Tabela por edge --
    edge_rows = []
    for edge in ("strong", "moderate", "weak", "insufficient"):
        seg = perf["by_edge"].get(edge)
        if not seg:
            continue
        wr_e  = seg["win_rate"]
        rc    = color(seg["roi"], 0)
        edge_rows.append(
            f"<tr>"
            f"<td style='{TD}'>{_EDGE_LABELS.get(edge, edge)}</td>"
            f"<td style='{TDN}'>{seg['n']}</td>"
            f"<td style='{TD};color:{color(wr_e, 0.50)};font-weight:600'>{wr_e:.1%}</td>"
            f"<td style='{TD};color:{rc}'>{seg['roi']:+.2f}u</td>"
            f"</tr>"
        )
    edge_rows_html = "".join(edge_rows)

    # -- Tabela por mercado --
    mkt_rows = []
    for mkt in ("o25", "btts", "1x2"):
        seg = perf["by_market"].get(mkt)
        if not seg:
            continue
        wr_m = seg["win_rate"]
        rc   = color(seg["roi"], 0)
        mkt_rows.append(
            f"<tr>"
            f"<td style='{TD}'>{MARKET_LABELS.get(mkt, mkt)}</td>"
            f"<td style='{TDN}'>{seg['n']}</td>"
            f"<td style='{TD};color:{color(wr_m, 0.50)};font-weight:600'>{wr_m:.1%}</td>"
            f"<td style='{TD};color:{rc}'>{seg['roi']:+.2f}u</td>"
            f"</tr>"
        )
    mkt_rows_html = "".join(mkt_rows)

    tables_html = (
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px'>"
        f"<div>"
        f"<div style='font-size:.70rem;color:oklch(55% 0.014 82);text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px'>Por Sinal de Edge</div>"
        f"<table style='{TS}'>"
        f"<thead><tr><th style='{TH}'>Sinal</th><th style='{TH}'>n</th><th style='{TH}'>Acerto</th><th style='{TH}'>ROI</th></tr></thead>"
        f"<tbody>{edge_rows_html}</tbody></table>"
        f"</div>"
        f"<div>"
        f"<div style='font-size:.70rem;color:oklch(55% 0.014 82);text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px'>Por Mercado</div>"
        f"<table style='{TS}'>"
        f"<thead><tr><th style='{TH}'>Mercado</th><th style='{TH}'>n</th><th style='{TH}'>Acerto</th><th style='{TH}'>ROI</th></tr></thead>"
        f"<tbody>{mkt_rows_html}</tbody></table>"
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
        line_color = "#40b89a" if roi >= 0 else "#c04539"
        bg_color   = "rgba(64,184,154,0.07)" if roi >= 0 else "rgba(192,69,57,0.07)"
        chart_html = f"""
<div style='margin-bottom:18px'>
  <div style='font-size:.70rem;color:oklch(55% 0.014 82);text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px'>ROI Acumulado ({n} picks resolvidas)</div>
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
          borderColor: '#2a2a28',
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
        x: {{ ticks: {{ color: '#989490', maxTicksLimit: 12 }}, grid: {{ color: '#232322' }} }},
        y: {{ ticks: {{ color: '#989490' }}, grid: {{ color: '#232322' }} }}
      }}
    }}
  }});
}})();
</script>"""

    # -- Tabela de picks recentes --
    recent = perf.get("recent", [])
    recent_rows = []
    for p in recent[:15]:
        hit_s   = "✅" if p.get("hit") else "❌"
        profit  = (p["odds"] - 1) if p.get("hit") else -1.0
        p_color = "oklch(70% 0.12 188)" if profit > 0 else "oklch(58% 0.15 35)"
        edge_s  = _EDGE_LABELS.get(p.get("edge", ""), p.get("edge", ""))
        recent_rows.append(
            f"<tr>"
            f"<td style='color:oklch(63% 0.024 82)'>{p.get('date','')}</td>"
            f"<td>{escape(p.get('home',''))} vs {escape(p.get('away',''))}</td>"
            f"<td style='color:oklch(63% 0.024 82)'>{MARKET_LABELS.get(p.get('market',''), p.get('market',''))}</td>"
            f"<td style='font-size:.75rem'>{edge_s}</td>"
            f"<td style='text-align:center;font-size:1.05rem'>{hit_s}</td>"
            f"<td style='color:{p_color};text-align:right'>{profit:+.2f}u</td>"
            f"</tr>"
        )
    recent_rows_html = "".join(recent_rows)

    recent_html = ""
    if recent_rows_html:
        recent_html = (
            f"<div style='font-size:.70rem;color:oklch(55% 0.014 82);text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px'>Picks Recentes</div>"
            f"<div style='overflow-x:auto'><table style='{TS}'>"
            f"<thead><tr>"
            f"<th style='{TH}'>Data</th>"
            f"<th style='{TH}'>Jogo</th>"
            f"<th style='{TH}'>Mercado</th>"
            f"<th style='{TH}'>Edge</th>"
            f"<th style='{TH};text-align:center'>Res.</th>"
            f"<th style='{TH};text-align:right'>P&L</th>"
            f"</tr></thead>"
            f"<tbody>{recent_rows_html}</tbody>"
            f"</table></div>"
            f"<p style='font-size:.70rem;color:oklch(55% 0.014 82);margin-top:6px'>ROI calculado com odds-base por mercado (O2.5 1.90x · BTTS 1.85x · 1X2 2.20x) · 1u por pick</p>"
        )

    return (
        f"<div class='card'>"
        f"<h3>Performance do Analista — Backtest Próprio · {n} resolvidas · {pending} pendentes</h3>"
        f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px;font-size:.90rem'>"
        f"<div>Taxa de Acerto: <b style='color:{wr_c}'>{wr:.1%}</b> <span style='color:oklch(55% 0.014 82)'>({wins}W / {losses}L)</span></div>"
        f"<div>ROI: <b style='color:{roi_c}'>{roi:+.2f}u</b> <span style='color:oklch(55% 0.014 82)'>({roi_pct:+.1f}%/pick)</span></div>"
        f"</div>"
        f"{tables_html}"
        f"{chart_html}"
        f"{recent_html}"
        f"</div>"
    )


def gen_dashboard_today(today_stats):
    os.makedirs(DOCS_DIR, exist_ok=True)
    now      = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    backtest_n    = today_stats.get("backtest_n", 0)
    total_games   = today_stats.get("total_games", 0)
    total_picks   = today_stats.get("total_picks", 0)
    strong_picks  = today_stats.get("strong_picks", 0)
    today_str     = today_stats.get("today", "")
    tomorrow_str  = today_stats.get("tomorrow", "")
    all_games     = today_stats.get("games", [])
    games_today    = [g for g in all_games if g.get("date") == today_str]
    games_tomorrow = [g for g in all_games if g.get("date") == tomorrow_str]
    global_stats  = today_stats.get("global_stats", {})
    conf_stats    = today_stats.get("conf_stats", {})
    tracker       = today_stats.get("tracker", {"total_resolved": 0, "total_pending": 0})

    # --- Backtest context table ---
    def _bt_row(market_key, label):
        gs = global_stats.get(market_key, {})
        rows = [f"<td style='padding:5px 10px;color:oklch(63% 0.024 82);font-size:.78rem'>{label}</td>"]
        for conf in ("ALTA", "MÉDIA", "BAIXA"):
            cs = conf_stats.get(conf, {}).get(market_key, {})
            n  = cs.get("n", 0)
            wr = cs.get("win_rate", 0)
            ci_l = cs.get("ci_low", 0)
            ci_h = cs.get("ci_high", 1)
            if n >= 5:
                c    = color(wr, 1 / MARKET_BASE_ODDS.get(market_key, 2.0))
                warn = " ⚠" if not cs.get("reliable") else ""
                rows.append(f"<td style='padding:5px 10px;color:{c}'>{pct(wr)}<br><span style='color:oklch(55% 0.014 82);font-size:.70rem'>(n={n}{warn}) [{ci_l:.0%}–{ci_h:.0%}]</span></td>")
            else:
                rows.append("<td style='padding:5px 10px;color:oklch(55% 0.014 82);font-size:.78rem'>insuf.</td>")
        n_g  = gs.get("n", 0)
        wr_g = gs.get("win_rate", 0)
        ci_gl = gs.get("ci_low", 0)
        ci_gh = gs.get("ci_high", 1)
        if n_g >= 5:
            c    = color(wr_g, 1 / MARKET_BASE_ODDS.get(market_key, 2.0))
            warn = " ⚠" if not gs.get("reliable") else ""
            rows.append(f"<td style='padding:5px 10px;color:{c}'><b>{pct(wr_g)}</b><br><span style='color:oklch(55% 0.014 82);font-size:.70rem'>(n={n_g}{warn}) [{ci_gl:.0%}–{ci_gh:.0%}]</span></td>")
        else:
            rows.append("<td style='padding:5px 10px;color:oklch(55% 0.014 82);font-size:.78rem'>insuf.</td>")
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
  <p style='color:oklch(55% 0.014 82);font-size:.72rem;margin-top:8px'>
    ⚠ n&lt;20 = amostra insuficiente · IC = intervalo de confiança Wilson 95% ·
    Break-even: O2.5&nbsp;52.6%, BTTS&nbsp;54.1%, 1X2&nbsp;45.5%
  </p>
</div>"""

    def _build_cards(game_list):
        if not game_list:
            return ""
        cards = []
        for g in game_list:
            # Game header
            conf_b = _conf_badge(g["conf"]) if g["conf"] in ("ALTA", "MÉDIA") else ""
            ko_raw = str(g["ko_hour"]) if g["ko_hour"] else ""
            ko     = (f"🕐 {ko_raw}" if ":" in ko_raw else f"🕐 {ko_raw}:00") if ko_raw else ""
            picks_html = "".join(_pick_card(p) for p in g["picks"])

            # Model probabilities
            probs = []
            if g["prob_o25"] > 0:
                c = "oklch(70% 0.12 188)" if g["prob_o25"] >= 60 else "oklch(63% 0.024 82)"
                probs.append(f"<span style='color:{c}'>O2.5 <b>{g['prob_o25']:.0f}%</b></span>")
            if g["prob_btts"] > 0:
                c = "oklch(70% 0.12 188)" if g["prob_btts"] >= 60 else "oklch(63% 0.024 82)"
                probs.append(f"<span style='color:{c}'>BTTS <b>{g['prob_btts']:.0f}%</b></span>")
            if g["xg_total"] > 0:
                probs.append(f"<span style='color:oklch(63% 0.024 82)'>xG <b>{g['xg_total']:.1f}</b></span>")
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
                    p1x2_html = f"<div style='color:oklch(63% 0.024 82);font-size:.78rem;margin-top:4px'>1X2: {' · '.join(dirs)}</div>"

            n_strong   = g["n_strong"]
            n_moderate = g["n_moderate"]
            card_border = "oklch(70% 0.12 188 / 0.5)" if n_strong > 0 else ("oklch(84% 0.19 80.46 / 0.4)" if n_moderate > 0 else "oklch(28% 0.010 95)")

            cards.append(f"""
<div class='card' style='border-color:{card_border}'>
  <div style='display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;margin-bottom:10px'>
    <div>
      <div style='font-size:.78rem;color:oklch(63% 0.024 82);margin-bottom:3px'>{escape(g['league'])}</div>
      <div class='teams'><b>{escape(g['home'])}</b> <span style='color:oklch(55% 0.014 82)'>vs</span> <b>{escape(g['away'])}</b></div>
    </div>
    <div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap'>
      {conf_b}
      <span style='color:oklch(63% 0.024 82);font-size:.8rem'>{ko}</span>
    </div>
  </div>
  {picks_html}
  <div style='margin-top:8px;font-size:.78rem;color:oklch(55% 0.014 82)'>{probs_html}{p1x2_html}</div>
</div>""")

        return "\n".join(cards)

    def _empty_section(label):
        return f"""
<div style='background:oklch(11% 0.006 95);border:1px solid oklch(28% 0.010 95);border-radius:2px;padding:24px;text-align:center;color:oklch(63% 0.024 82);margin-bottom:16px'>
  <div style='font-size:1.5rem;margin-bottom:8px'>📭</div>
  <div style='font-size:.9rem;color:oklch(84% 0.035 82)'>Sem jogos com picks disponíveis {label}</div>
  <div style='font-size:.78rem;margin-top:6px'>O pipeline do football-dashboard ainda não processou estes jogos.</div>
</div>"""

    def _section_header(label, date_str, game_list):
        n_g = len(game_list)
        n_s = sum(g["n_strong"] for g in game_list)
        strong_note = f' · <span style="color:oklch(70% 0.12 188)">{n_s} fortes</span>' if n_s else ""
        return (f"<h2 style='color:oklch(84% 0.035 82);font-size:1rem;margin:24px 0 12px'>"
                f"{label} <span style='color:oklch(55% 0.014 82);font-size:.82rem'>· {date_str}</span>"
                f" — {n_g} jogo{'s' if n_g != 1 else ''} com picks{strong_note}</h2>")

    today_pt_label    = datetime.strptime(today_str,    "%Y-%m-%d").strftime("%d/%m") if today_str    else ""
    tomorrow_pt_label = datetime.strptime(tomorrow_str, "%Y-%m-%d").strftime("%d/%m") if tomorrow_str else ""

    games_html = (
        _section_header("Hoje", today_pt_label, games_today)
        + (_build_cards(games_today) or _empty_section("para hoje"))
        + _section_header("Amanhã", tomorrow_pt_label, games_tomorrow)
        + (_build_cards(games_tomorrow) or _empty_section("para amanhã"))
    )

    # --- Tracker KPIs ---
    t_n       = tracker.get("total_resolved", 0)
    t_pending = tracker.get("total_pending",  0)
    t_wr      = tracker.get("win_rate",  0.0)
    t_roi     = tracker.get("roi",       0.0)
    t_wr_c    = "oklch(70% 0.12 188)" if t_wr >= 0.50 else ("oklch(63% 0.024 82)" if t_n == 0 else "oklch(58% 0.15 35)")
    t_roi_c   = "oklch(70% 0.12 188)" if t_roi >= 0   else ("oklch(63% 0.024 82)" if t_n == 0 else "oklch(58% 0.15 35)")
    t_wr_s    = f"{t_wr:.1%}" if t_n > 0 else "—"
    t_roi_s   = f"{t_roi:+.2f}u" if t_n > 0 else "—"

    tracker_section_html = _tracker_section(tracker)

    # --- Summary strip ---
    summary_items = [
        f"<div class='kpi'><div class='kpi-l'>Jogos c/ Picks</div><div class='kpi-v' style='color:oklch(84% 0.19 80.46)'>{total_games}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Fortes ✅</div><div class='kpi-v' style='color:oklch(70% 0.12 188)'>{strong_picks}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Moderadas ⚠️</div><div class='kpi-v' style='color:oklch(48% 0.12 80)'>{sum(g['n_moderate'] for g in all_games)}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Rastreadas</div><div class='kpi-v' style='color:oklch(63% 0.024 82)'>{t_n + t_pending}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Acerto Próprio</div><div class='kpi-v' style='color:{t_wr_c}'>{t_wr_s}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>ROI Próprio</div><div class='kpi-v' style='color:{t_roi_c}'>{t_roi_s}</div></div>",
    ]
    summary_html = "\n".join(summary_items)

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Onde Apostar Hoje e Amanhã — Analista</title>
<meta http-equiv="refresh" content="900">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Albert+Sans:wght@300;400;500;600&family=Alumni+Sans+Pinstripe&display=swap');
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:oklch(7% 0.006 95);color:oklch(81% 0.03 82);font-family:"Albert Sans","Avenir Next","Helvetica Neue",Arial,system-ui,sans-serif;padding:20px;font-size:14px}}
h1{{font-size:1.5rem;color:oklch(84% 0.19 80.46);margin-bottom:4px;font-family:"Alumni Sans Pinstripe","Albert Sans",sans-serif;font-weight:300;letter-spacing:.02em;}}
.sub{{color:oklch(63% 0.024 82);font-size:.82rem;margin-bottom:20px;font-family:"SFMono-Regular","Roboto Mono",Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;font-size:.72rem;}}
.kpi-bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}}
.kpi{{background:oklch(11% 0.006 95);border:1px solid oklch(28% 0.010 95);border-radius:2px;padding:12px 18px;min-width:130px}}
.kpi-l{{font-size:.72rem;color:oklch(63% 0.024 82);text-transform:uppercase;letter-spacing:.05em}}
.kpi-v{{font-size:1.4rem;font-weight:700;margin-top:3px}}
.card{{background:oklch(11% 0.006 95);border:1px solid oklch(28% 0.010 95);border-radius:2px;padding:18px;margin-bottom:16px}}
.card h3{{font-size:.80rem;color:oklch(63% 0.024 82);margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;color:oklch(63% 0.024 82);padding:5px 8px;border-bottom:1px solid oklch(28% 0.010 95);font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid oklch(15% 0.008 95);vertical-align:top}}
tr:last-child td{{border-bottom:none}}
.teams{{font-size:1.05rem;color:oklch(84% 0.035 82)}}
.conf-badge{{font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:2px}}
.market-pill{{font-size:.88rem;font-weight:700;color:oklch(84% 0.035 82)}}
.edge-badge{{font-size:.72rem;padding:2px 8px;border-radius:2px;font-weight:600}}
.edge-strong{{background:oklch(11% 0.006 95);color:oklch(70% 0.12 188);border:1px solid oklch(70% 0.12 188 / 0.45)}}
.edge-moderate{{background:oklch(11% 0.006 95);color:oklch(84% 0.19 80.46);border:1px solid oklch(84% 0.19 80.46 / 0.45)}}
.edge-weak{{background:oklch(11% 0.006 95);color:oklch(58% 0.15 35);border:1px solid oklch(58% 0.15 35 / 0.45)}}
.edge-insuf{{background:oklch(11% 0.006 95);color:oklch(63% 0.024 82);border:1px solid oklch(28% 0.010 95)}}
.stat-line{{font-size:.80rem;color:oklch(63% 0.024 82);margin-bottom:3px;line-height:1.5}}
.stat-key{{color:oklch(55% 0.014 82)}}
.kelly-line{{margin-top:5px;padding-top:5px;border-top:1px solid oklch(15% 0.008 95)}}
.legend{{background:oklch(11% 0.006 95);border:1px solid oklch(28% 0.010 95);border-radius:2px;padding:12px 16px;margin-bottom:20px;font-size:.78rem;color:oklch(63% 0.024 82);line-height:1.7}}
@media(max-width:650px){{.kpi-bar{{gap:8px}}}}
</style>
</head>
<body>
<h1>🎯 Onde Apostar Hoje e Amanhã</h1>
<p class="sub">Actualizado: {now} · picks do Matemática Da Bola qualificados pelo backtest</p>

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

{games_html}

<p style='text-align:center;color:oklch(55% 0.014 82);font-size:.75rem;margin-top:20px'>
  Analista · Baseado no backtest do Matemática Da Bola · nunovinhas-creator/Analista
</p>
</body>
</html>"""

    with open(f"{DOCS_DIR}/today_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] today_dashboard.html gerado")
