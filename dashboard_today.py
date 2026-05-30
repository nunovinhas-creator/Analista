# dashboard_today.py — Gera docs/today_dashboard.html ("Onde Apostar Hoje")
import json
import os
from datetime import datetime, timezone

DOCS_DIR = "docs"

_BREAK_EVEN = {"o25": 1/1.90, "btts": 1/1.85, "1x2": 1/2.20}
_MKT_LABELS = {"o25": "Over 2.5", "btts": "BTTS", "1x2": "1X2"}
_EDGE_LABELS = {
    "strong":       "✅ Forte",
    "moderate":     "⚠️ Moderado",
    "weak":         "❌ Fraco",
    "insufficient": "📊 Insuf.",
    "seeded":       "📂 Histórico",
}


def _pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def _color(v, threshold=0.0):
    return "#3fb950" if v >= threshold else "#f85149"


def _fmt_ko(ko):
    if not ko:
        return ""
    s = str(ko).strip()
    if ":" in s:
        return f"🕐 {s}"
    return f"🕐 {s}:00"


def _edge_badge(edge):
    styles = {
        "strong":       "background:#0d2818;color:#3fb950;border:1px solid #166534",
        "moderate":     "background:#1c1a00;color:#d29922;border:1px solid #7d6608",
        "weak":         "background:#1c0a0a;color:#f85149;border:1px solid #7f1d1d",
        "insufficient": "background:#161b22;color:#6e7681;border:1px solid #30363d",
    }
    s = styles.get(edge, styles["insufficient"])
    return f"<span style='font-size:.72rem;padding:2px 8px;border-radius:10px;font-weight:600;{s}'>{_EDGE_LABELS.get(edge, edge)}</span>"


def _conf_badge(conf):
    styles = {
        "ALTA":  "background:#0d2818;color:#3fb950;border:1px solid #166534",
        "MÉDIA": "background:#1c1a00;color:#d29922;border:1px solid #7d6608",
        "BAIXA": "background:#1c0a0a;color:#f85149;border:1px solid #7f1d1d",
    }
    s = styles.get(conf, "background:#161b22;color:#8b949e;border:1px solid #30363d")
    return f"<span style='font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:12px;{s}'>{conf}</span>"


def _dir_label(d):
    return {"H": "Casa", "A": "Fora", "D": "Empate", None: ""}.get(d, "")


def _pick_card(pick):
    edge      = pick["edge"]
    label     = pick["label"]
    ref_label = pick["ref_label"]
    ref_wr    = pick["ref_wr"]
    ref_n     = pick["ref_n"]
    ref_ci_l  = pick["ref_ci_l"]
    ref_ci_h  = pick["ref_ci_h"]
    global_wr = pick["global_wr"]
    global_n  = pick["global_n"]
    league_n  = pick["league_n"]
    league_wr = pick["league_wr"]
    kq        = pick["kelly_pct"]
    odds      = pick["odds"]
    be        = 1.0 / odds

    border_color = {"strong": "#166534", "moderate": "#7d6608"}.get(edge, "#30363d")
    bg_color     = {"strong": "#0d2818", "moderate": "#1c1a00"}.get(edge, "#161b22")

    dir_s  = _dir_label(pick.get("dir"))
    mkt_title = label + (f" <span style='font-size:.78rem;color:#8b949e'>({dir_s})</span>" if dir_s else "")

    # Linha de referência (liga / conf / global)
    ref_src = ref_label if ref_label in ("liga", "ALTA", "MÉDIA", "BAIXA") else "global"
    warn_n  = " <span style='color:#d29922;font-size:.72rem'>⚠ n&lt;20</span>" if not pick["ref_reliable"] else ""
    ref_line = (f"<div class='stat-line'>"
                f"<span class='stat-key'>Ref. {ref_src}:</span>"
                f" <b style='color:{_color(ref_wr, be)}'>{_pct(ref_wr)}</b>"
                f" (n={ref_n})"
                f" <span style='color:#6e7681'>[{ref_ci_l:.0%}–{ref_ci_h:.0%}]</span>"
                f"{warn_n}</div>")

    # Linha global (se a ref não for já global e tiver dados)
    global_line = ""
    if ref_label != "global" and global_n >= 10:
        global_line = (f"<div class='stat-line'>"
                       f"<span class='stat-key'>Global:</span>"
                       f" <span style='color:{_color(global_wr, be)}'>{_pct(global_wr)}</span>"
                       f" (n={global_n})</div>")

    # Linha da liga (se tiver dados e não for já a ref)
    league_line = ""
    if league_n >= 10 and ref_label != "liga":
        lw  = " <span style='color:#d29922;font-size:.72rem'>⚠ n&lt;20</span>" if league_n < 20 else ""
        lci = f" <span style='color:#6e7681'>[{pick['league_ci_l']:.0%}–{pick['league_ci_h']:.0%}]</span>"
        league_line = (f"<div class='stat-line'>"
                       f"<span class='stat-key'>Liga:</span>"
                       f" <b style='color:{_color(league_wr, be)}'>{_pct(league_wr)}</b>"
                       f" (n={league_n}){lci}{lw}</div>")

    # Linha Kelly
    if edge in ("strong", "moderate") and kq > 0:
        kc = "#3fb950" if edge == "strong" else "#d29922"
        kelly_line = (f"<div class='stat-line kelly-line'>"
                      f"<span class='stat-key'>Kelly ¼:</span>"
                      f" <b style='color:{kc}'>{kq:.1f}% da banca</b>"
                      f" <span style='color:#6e7681'>(odds {odds:.2f}x)</span></div>")
    elif not pick["ref_reliable"]:
        kelly_line = "<div class='stat-line'><span style='color:#6e7681;font-size:.78rem'>Amostra insuficiente (n&lt;20) — stake não recomendado</span></div>"
    elif edge == "weak":
        kelly_line = "<div class='stat-line'><span style='color:#6e7681;font-size:.78rem'>EV negativo — sem aposta</span></div>"
    else:
        kelly_line = "<div class='stat-line'><span style='color:#6e7681;font-size:.78rem'>Dados insuficientes</span></div>"

    return (f"<div style='background:{bg_color};border:1px solid {border_color};"
            f"border-radius:8px;padding:12px 14px;margin-bottom:8px'>"
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>"
            f"<span style='font-size:.88rem;font-weight:700;color:#e6edf3'>{mkt_title}</span>"
            f"{_edge_badge(edge)}</div>"
            f"{ref_line}{global_line}{league_line}{kelly_line}</div>")


def _top_picks_section(top_picks):
    if not top_picks:
        return ""

    rows = ""
    for p in top_picks:
        ko_s    = _fmt_ko(p.get("ko_hour", ""))
        dir_s   = _dir_label(p.get("dir"))
        mkt_s   = _MKT_LABELS.get(p["market"], p["market"])
        mkt_dir = mkt_s + (f" ({dir_s})" if dir_s else "")
        ref_s   = f"{_pct(p['ref_wr'])} n={p['ref_n']}" if p["ref_n"] >= 5 else "—"
        kq_s    = (f"<b style='color:#3fb950'>{p['kelly_pct']:.1f}% banca</b>"
                   if p.get("kelly_pct", 0) > 0 and p.get("ref_reliable")
                   else "<span style='color:#6e7681'>—</span>")
        rows += (f"<tr>"
                 f"<td style='padding:6px 10px'><b style='color:#e6edf3'>{p['home']}</b>"
                 f" <span style='color:#6e7681'>vs</span> <b style='color:#e6edf3'>{p['away']}</b>"
                 f"<br><span style='font-size:.72rem;color:#8b949e'>{p['league']} · {ko_s}</span></td>"
                 f"<td style='padding:6px 10px'>{mkt_dir}</td>"
                 f"<td style='padding:6px 10px'>{_edge_badge(p['edge'])}</td>"
                 f"<td style='padding:6px 10px;color:#8b949e;font-size:.80rem'>{ref_s}</td>"
                 f"<td style='padding:6px 10px'>{kq_s}</td>"
                 f"</tr>")

    TH = "text-align:left;color:#6e7681;padding:5px 10px;border-bottom:1px solid #21262d;font-weight:500;font-size:.75rem;text-transform:uppercase"
    return (f"<div class='card' style='border-color:#166534'>"
            f"<h3>🎯 Top Picks do Dia</h3>"
            f"<div style='overflow-x:auto'>"
            f"<table style='width:100%;border-collapse:collapse;font-size:.85rem'>"
            f"<thead><tr>"
            f"<th style='{TH}'>Jogo</th>"
            f"<th style='{TH}'>Mercado</th>"
            f"<th style='{TH}'>Edge</th>"
            f"<th style='{TH}'>Referência</th>"
            f"<th style='{TH}'>Stake</th>"
            f"</tr></thead>"
            f"<tbody>{rows}</tbody>"
            f"</table></div></div>")


def _tracker_section(perf):
    pending   = perf.get("total_pending", 0)
    seeded    = perf.get("seeded", {})
    tracked   = perf.get("tracked", {})
    n_seeded  = seeded.get("total", 0) if seeded else 0
    n_tracked = tracked.get("total", 0) if tracked else 0

    # --- Calibração histórica (seeded) ---
    if n_seeded:
        wr_s  = seeded.get("win_rate", 0)
        roi_s = seeded.get("roi", 0)
        wr_sc = "#3fb950" if wr_s >= 0.50 else "#f85149"
        roi_sc = "#3fb950" if roi_s >= 0 else "#f85149"
        seeded_html = (f"<div style='padding:10px 14px;background:#0d1117;border-radius:6px;margin-bottom:12px'>"
                       f"<div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;margin-bottom:6px'>"
                       f"📂 Calibração histórica (picks do MDB resolvidos)</div>"
                       f"<div style='display:flex;gap:20px;flex-wrap:wrap;font-size:.85rem'>"
                       f"<div>{n_seeded} picks · "
                       f"WR <b style='color:{wr_sc}'>{_pct(wr_s)}</b> · "
                       f"ROI <b style='color:{roi_sc}'>{roi_s:+.1f}u</b></div></div>"
                       f"<div style='font-size:.72rem;color:#6e7681;margin-top:4px'>"
                       f"Base histórica — confirma que os mercados seleccionados têm EV positivo no corpus do MDB</div>"
                       f"</div>")
    else:
        seeded_html = ""

    # --- Backtest próprio (picks rastreadas) ---
    if n_tracked == 0:
        tracked_html = (f"<div style='text-align:center;padding:20px;color:#8b949e'>"
                        f"<div style='font-size:1.4rem;margin-bottom:8px'>📊</div>"
                        f"<div>A acumular dados — {pending} pick{'s' if pending != 1 else ''} pendente{'s' if pending != 1 else ''}</div>"
                        f"<div style='font-size:.75rem;margin-top:5px'>As picks identificadas hoje serão resolvidas automaticamente quando os resultados ficarem disponíveis.</div>"
                        f"</div>")
    else:
        wr_t   = tracked.get("win_rate", 0)
        roi_t  = tracked.get("roi", 0)
        rp_t   = tracked.get("roi_pct", 0)
        wins_t = tracked.get("wins", 0)
        loss_t = tracked.get("losses", 0)
        wr_tc  = "#3fb950" if wr_t >= 0.50 else "#f85149"
        roi_tc = "#3fb950" if roi_t >= 0 else "#f85149"

        TS  = "width:100%;border-collapse:collapse;font-size:.82rem"
        TH  = "text-align:left;color:#6e7681;padding:4px 8px;border-bottom:1px solid #21262d;font-weight:500"
        TD  = "padding:4px 8px;border-bottom:1px solid #21262d"
        TDN = "padding:4px 8px;border-bottom:1px solid #21262d;color:#8b949e"

        def _pos(v):
            return "#3fb950" if v >= 0 else "#f85149"

        def _wrc(v, be=0.50):
            return "#3fb950" if v >= be else "#f85149"

        edge_rows = ""
        for edge in ("strong", "moderate", "weak"):
            seg = (tracked.get("by_edge") or {}).get(edge)
            if not seg:
                continue
            rc = _pos(seg["roi"])
            wr = seg["win_rate"]
            edge_rows += (f"<tr>"
                          f"<td style='{TD}'>{_EDGE_LABELS.get(edge, edge)}</td>"
                          f"<td style='{TDN}'>{seg['n']}</td>"
                          f"<td style='{TD};color:{_wrc(wr)};font-weight:600'>{_pct(wr)}</td>"
                          f"<td style='{TD};color:{rc}'>{seg['roi']:+.2f}u</td>"
                          f"</tr>")

        mkt_rows = ""
        for mkt in ("btts", "o25", "1x2"):
            seg = (tracked.get("by_market") or {}).get(mkt)
            if not seg:
                continue
            be_mkt = {"o25": 1/1.90, "btts": 1/1.85, "1x2": 1/2.20}.get(mkt, 0.5)
            rc = _pos(seg["roi"])
            wr = seg["win_rate"]
            mkt_rows += (f"<tr>"
                         f"<td style='{TD}'>{_MKT_LABELS.get(mkt, mkt)}</td>"
                         f"<td style='{TDN}'>{seg['n']}</td>"
                         f"<td style='{TD};color:{_wrc(wr, be_mkt)};font-weight:600'>{_pct(wr)}</td>"
                         f"<td style='{TD};color:{rc}'>{seg['roi']:+.2f}u</td>"
                         f"</tr>")

        tables_html = (f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px'>"
                       f"<div><div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;margin-bottom:6px'>Por Edge</div>"
                       f"<table style='{TS}'><thead><tr>"
                       f"<th style='{TH}'>Sinal</th><th style='{TH}'>n</th>"
                       f"<th style='{TH}'>Acerto</th><th style='{TH}'>ROI</th></tr></thead>"
                       f"<tbody>{edge_rows}</tbody></table></div>"
                       f"<div><div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;margin-bottom:6px'>Por Mercado</div>"
                       f"<table style='{TS}'><thead><tr>"
                       f"<th style='{TH}'>Mercado</th><th style='{TH}'>n</th>"
                       f"<th style='{TH}'>Acerto</th><th style='{TH}'>ROI</th></tr></thead>"
                       f"<tbody>{mkt_rows}</tbody></table></div></div>")

        # Gráfico ROI acumulado
        chart_html = ""
        series = (tracked.get("series") or [])
        if len(series) >= 2:
            s_data     = json.dumps([s["cum"] for s in series])
            s_tooltips = json.dumps([f"{s['date']} · {s['label']} ({s['market']}) {'✅' if s['hit'] else '❌'}"
                                     for s in series])
            s_labels   = json.dumps(list(range(1, len(series) + 1)))
            zero_arr   = json.dumps([0] * len(series))
            lc  = "#3fb950" if roi_t >= 0 else "#f85149"
            bgc = "rgba(63,185,80,0.07)" if roi_t >= 0 else "rgba(248,81,73,0.07)"
            pr  = 3 if len(series) <= 50 else 0
            chart_html = (
                f"<div style='margin-bottom:18px'>"
                f"<div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;margin-bottom:8px'>"
                f"ROI Acumulado ({n_tracked} picks rastreadas)</div>"
                f"<canvas id='trackerChart' height='80'></canvas></div>"
                f"<script>(function(){{"
                f"var tt={s_tooltips};"
                f"new Chart(document.getElementById('trackerChart').getContext('2d'),{{"
                f"type:'line',data:{{labels:{s_labels},datasets:["
                f"{{label:'ROI',data:{s_data},borderColor:'{lc}',backgroundColor:'{bgc}',"
                f"fill:true,tension:0.15,pointRadius:{pr},pointHoverRadius:5,borderWidth:2}},"
                f"{{label:'',data:{zero_arr},borderColor:'#30363d',borderDash:[4,4],"
                f"pointRadius:0,fill:false,borderWidth:1}}]}},"
                f"options:{{responsive:true,plugins:{{legend:{{display:false}},"
                f"tooltip:{{callbacks:{{title:function(i){{return tt[i[0].dataIndex]||''}},"
                f"label:function(i){{return 'ROI: '+i.raw.toFixed(2)+'u'}}}}}}}},"
                f"scales:{{x:{{ticks:{{color:'#8b949e',maxTicksLimit:12}},grid:{{color:'#21262d'}}}},"
                f"y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}}}}}}}});}})();</script>"
            )

        # Tabela picks recentes
        recent = (tracked.get("recent") or [])
        recent_rows = ""
        for p in recent[:15]:
            hit_s   = "✅" if p.get("hit") else "❌"
            profit  = (p["odds"] - 1) if p.get("hit") else -1.0
            pc      = "#3fb950" if profit > 0 else "#f85149"
            edge_s  = _EDGE_LABELS.get(p.get("edge", ""), p.get("edge", ""))
            recent_rows += (f"<tr>"
                            f"<td style='{TD};color:#8b949e'>{p.get('date','')}</td>"
                            f"<td style='{TD}'>{p.get('home','')} vs {p.get('away','')}</td>"
                            f"<td style='{TD};color:#8b949e'>{_MKT_LABELS.get(p.get('market',''), '')}</td>"
                            f"<td style='{TD};font-size:.75rem'>{edge_s}</td>"
                            f"<td style='{TD};text-align:center'>{hit_s}</td>"
                            f"<td style='{TD};color:{pc};text-align:right'>{profit:+.2f}u</td>"
                            f"</tr>")

        recent_html = ""
        if recent_rows:
            recent_html = (f"<div style='font-size:.70rem;color:#6e7681;text-transform:uppercase;margin-bottom:6px'>Picks Recentes</div>"
                           f"<div style='overflow-x:auto'><table style='{TS}'>"
                           f"<thead><tr>"
                           f"<th style='{TH}'>Data</th><th style='{TH}'>Jogo</th>"
                           f"<th style='{TH}'>Mercado</th><th style='{TH}'>Edge</th>"
                           f"<th style='{TH};text-align:center'>Res.</th>"
                           f"<th style='{TH};text-align:right'>P&L</th></tr></thead>"
                           f"<tbody>{recent_rows}</tbody></table></div>"
                           f"<p style='font-size:.70rem;color:#6e7681;margin-top:6px'>"
                           f"Odds: O2.5 1.90x · BTTS 1.85x · 1X2 2.20x · 1u por pick</p>")

        tracked_html = (f"<div style='display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px;font-size:.90rem'>"
                        f"<div>{n_tracked} picks rastreadas · "
                        f"WR <b style='color:{wr_tc}'>{_pct(wr_t)}</b> ({wins_t}W/{loss_t}L)</div>"
                        f"<div>ROI <b style='color:{roi_tc}'>{roi_t:+.2f}u</b> ({rp_t:+.1f}%/pick)</div>"
                        f"</div>"
                        f"{tables_html}{chart_html}{recent_html}")

    return (f"<div class='card'>"
            f"<h3>📈 Performance do Analista — Backtest Próprio</h3>"
            f"{seeded_html}{tracked_html}</div>")


def gen_dashboard_today(today_stats):
    os.makedirs(DOCS_DIR, exist_ok=True)
    now      = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    today_pt = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    backtest_n   = today_stats.get("backtest_n", 0)
    total_games  = today_stats.get("total_games", 0)
    total_picks  = today_stats.get("total_picks", 0)
    strong_picks = today_stats.get("strong_picks", 0)
    games        = today_stats.get("games", [])
    global_stats = today_stats.get("global_stats", {})
    conf_stats   = today_stats.get("conf_stats", {})
    tracker      = today_stats.get("tracker", {})
    top_picks    = today_stats.get("top_picks", [])

    # --- KPIs do tracker ---
    t_n    = tracker.get("total_resolved", 0)
    t_pend = tracker.get("total_pending",  0)
    t_wr   = tracker.get("win_rate",  0.0)
    t_roi  = tracker.get("roi",       0.0)
    t_wrc  = "#3fb950" if t_wr >= 0.50 else ("#8b949e" if t_n == 0 else "#f85149")
    t_roic = "#3fb950" if t_roi >= 0   else ("#8b949e" if t_n == 0 else "#f85149")
    t_wrs  = f"{t_wr:.1%}" if t_n > 0 else "—"
    t_rois = f"{t_roi:+.2f}u" if t_n > 0 else "—"

    # --- Secção Top Picks ---
    top_picks_html = _top_picks_section(top_picks)

    # --- Secção tracker ---
    tracker_html = _tracker_section(tracker)

    # --- Tabela backtest por conf×mercado ---
    def _bt_row(mk, label):
        gs   = global_stats.get(mk, {})
        be   = _BREAK_EVEN.get(mk, 0.5)
        odds = {"o25": 1.90, "btts": 1.85, "1x2": 2.20}.get(mk, 2.0)
        cells = [f"<td style='padding:5px 10px;color:#8b949e;font-size:.78rem'>{label}</td>"]
        for conf in ("ALTA", "MÉDIA", "BAIXA"):
            cs = conf_stats.get(conf, {}).get(mk, {})
            n  = cs.get("n", 0)
            wr = cs.get("win_rate", 0)
            cl, ch = cs.get("ci_low", 0), cs.get("ci_high", 1)
            if n >= 10:
                c    = _color(wr, be)
                warn = " ⚠" if not cs.get("reliable") else ""
                cells.append(f"<td style='padding:5px 10px;color:{c}'>{_pct(wr)}"
                              f"<br><span style='color:#6e7681;font-size:.70rem'>"
                              f"(n={n}{warn}) [{cl:.0%}–{ch:.0%}]</span></td>")
            else:
                cells.append("<td style='padding:5px 10px;color:#6e7681;font-size:.78rem'>insuf.</td>")
        n_g  = gs.get("n", 0)
        wr_g = gs.get("win_rate", 0)
        clg, chg = gs.get("ci_low", 0), gs.get("ci_high", 1)
        if n_g >= 10:
            c    = _color(wr_g, be)
            warn = " ⚠" if not gs.get("reliable") else ""
            cells.append(f"<td style='padding:5px 10px;color:{c}'><b>{_pct(wr_g)}</b>"
                         f"<br><span style='color:#6e7681;font-size:.70rem'>"
                         f"(n={n_g}{warn}) [{clg:.0%}–{chg:.0%}]</span></td>")
        else:
            cells.append("<td style='padding:5px 10px;color:#6e7681;font-size:.78rem'>insuf.</td>")
        return "<tr>" + "".join(cells) + "</tr>"

    backtest_table = (f"<div class='card'>"
                      f"<h3>Backtest — {backtest_n} jogos · Base estatística (threshold-based, odds reais)</h3>"
                      f"<table><thead><tr>"
                      f"<th style='padding:5px 10px'>Mercado</th>"
                      f"<th style='padding:5px 10px'>Conf ALTA</th>"
                      f"<th style='padding:5px 10px'>Conf MÉDIA</th>"
                      f"<th style='padding:5px 10px'>Conf BAIXA</th>"
                      f"<th style='padding:5px 10px'>Global</th>"
                      f"</tr></thead><tbody>"
                      f"{_bt_row('o25',  'Over 2.5 ≥60%')}"
                      f"{_bt_row('btts', 'BTTS ≥60%')}"
                      f"{_bt_row('1x2',  '1X2 ≥55% (A/M)')}"
                      f"</tbody></table>"
                      f"<p style='color:#6e7681;font-size:.72rem;margin-top:8px'>"
                      f"⚠ n&lt;20 = amostra insuficiente · IC Wilson 95% · "
                      f"Break-even: O2.5 52.6% · BTTS 54.1% · 1X2 45.5% · "
                      f"Kelly só calculado com n≥20</p></div>")

    # --- Cards dos jogos ---
    if not games:
        games_html = ("<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;"
                      "padding:32px;text-align:center;color:#8b949e'>"
                      "<div style='font-size:2rem;margin-bottom:12px'>📭</div>"
                      "<div style='font-size:1rem;color:#e6edf3'>Sem jogos com picks disponíveis para hoje</div>"
                      "<div style='font-size:.82rem;margin-top:8px'>"
                      "O pipeline do football-dashboard ainda não processou os jogos de hoje,<br>"
                      "ou nenhum jogo atingiu os limiares backtest (O2.5≥60%, BTTS≥60%, 1X2≥55%).</div></div>")
    else:
        cards = []
        for g in games:
            conf_b = _conf_badge(g["conf"])
            ko_s   = _fmt_ko(g["ko_hour"])
            picks_html = "".join(_pick_card(p) for p in g["picks"])

            # Bloco combinado BTTS+O2.5
            combo_html = ""
            if g.get("combined_btts_o25"):
                co = g.get("combined_odds", "")
                combo_html = (f"<div style='background:#1c1a00;border:1px solid #7d6608;"
                              f"border-radius:6px;padding:8px 12px;margin:8px 0;font-size:.82rem'>"
                              f"🔗 <b>Combinado potencial</b>: BTTS + O2.5"
                              f"<span style='color:#d29922'> · odds ~{co}x</span>"
                              f"<span style='color:#6e7681;font-size:.75rem'> — só apostar se ambos têm edge positivo</span>"
                              f"</div>")

            # Probabilidades do modelo
            probs = []
            if g["prob_o25"] > 0:
                c = "#3fb950" if g["prob_o25"] >= 60 else "#8b949e"
                probs.append(f"<span style='color:{c}'>O2.5 <b>{g['prob_o25']:.0f}%</b></span>")
            if g["prob_btts"] > 0:
                c = "#3fb950" if g["prob_btts"] >= 60 else "#8b949e"
                probs.append(f"<span style='color:{c}'>BTTS <b>{g['prob_btts']:.0f}%</b></span>")
            if g["xg_total"] > 0:
                probs.append(f"<span style='color:#8b949e'>xG <b>{g['xg_total']:.1f}</b></span>")
            probs_html = " · ".join(probs) if probs else ""

            p1x2_html = ""
            if any(p["market"] == "1x2" for p in g["picks"]):
                dirs = []
                if g["prob_hw"]: dirs.append(f"Casa {g['prob_hw']:.0f}%")
                if g["prob_dr"]: dirs.append(f"Emp {g['prob_dr']:.0f}%")
                if g["prob_aw"]: dirs.append(f"Fora {g['prob_aw']:.0f}%")
                if dirs:
                    p1x2_html = f"<div style='color:#8b949e;font-size:.78rem;margin-top:4px'>1X2: {' · '.join(dirs)}</div>"

            card_border = ("#166534" if g["n_strong"] > 0
                           else ("#7d6608" if g["n_moderate"] > 0 else "#30363d"))

            gs_badge = f"<span style='font-size:.72rem;color:#6e7681'>score {g['game_score']:.3f}</span>"

            cards.append(f"<div class='card' style='border-color:{card_border}'>"
                         f"<div style='display:flex;justify-content:space-between;align-items:flex-start;"
                         f"flex-wrap:wrap;gap:6px;margin-bottom:10px'>"
                         f"<div><div style='font-size:.78rem;color:#8b949e;margin-bottom:3px'>{g['league']}</div>"
                         f"<div style='font-size:1.05rem;color:#e6edf3'>"
                         f"<b>{g['home']}</b> <span style='color:#6e7681'>vs</span> <b>{g['away']}</b></div></div>"
                         f"<div style='display:flex;align-items:center;gap:8px;flex-wrap:wrap'>"
                         f"{conf_b} <span style='color:#8b949e;font-size:.8rem'>{ko_s}</span>"
                         f"{gs_badge}</div></div>"
                         f"{picks_html}{combo_html}"
                         f"<div style='margin-top:8px;font-size:.78rem;color:#6e7681'>{probs_html}{p1x2_html}</div>"
                         f"</div>")

        games_html = "\n".join(cards)

    # --- KPI bar ---
    n_mod = sum(g["n_moderate"] for g in games)
    summary_items = [
        f"<div class='kpi'><div class='kpi-l'>Jogos c/ Picks</div><div class='kpi-v' style='color:#58a6ff'>{total_games}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Fortes ✅</div><div class='kpi-v' style='color:#3fb950'>{strong_picks}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Picks Moderadas ⚠️</div><div class='kpi-v' style='color:#d29922'>{n_mod}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Rastreadas</div><div class='kpi-v' style='color:#8b949e'>{t_n + t_pend}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>Acerto Próprio</div><div class='kpi-v' style='color:{t_wrc}'>{t_wrs}</div></div>",
        f"<div class='kpi'><div class='kpi-l'>ROI Próprio</div><div class='kpi-v' style='color:{t_roic}'>{t_rois}</div></div>",
    ]
    summary_html = "\n".join(summary_items)

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Onde Apostar Hoje — Analista</title>
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
.kpi-v{{font-size:1.4rem;font-weight:700;margin-top:3px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;margin-bottom:16px}}
.card h3{{font-size:.80rem;color:#8b949e;margin-bottom:10px;text-transform:uppercase;letter-spacing:.04em}}
table{{width:100%;border-collapse:collapse;font-size:.83rem}}
th{{text-align:left;color:#8b949e;padding:5px 8px;border-bottom:1px solid #30363d;font-weight:500}}
td{{padding:5px 8px;border-bottom:1px solid #21262d;vertical-align:top}}
tr:last-child td{{border-bottom:none}}
.stat-line{{font-size:.80rem;color:#8b949e;margin-bottom:3px;line-height:1.5}}
.stat-key{{color:#6e7681}}
.kelly-line{{margin-top:5px;padding-top:5px;border-top:1px solid #21262d}}
details summary{{cursor:pointer;color:#8b949e;font-size:.78rem;user-select:none}}
details summary:hover{{color:#e6edf3}}
details[open] summary{{margin-bottom:8px}}
@media(max-width:650px){{.kpi-bar{{gap:8px}}}}
</style>
</head>
<body>
<h1>🎯 Onde Apostar Hoje</h1>
<p class="sub">Actualizado: {now} · {today_pt} · critérios derivados do backtest do Matemática Da Bola</p>

<div class="kpi-bar">
{summary_html}
</div>

<details style='margin-bottom:16px;background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 16px'>
<summary><b>ℹ Como ler este dashboard</b></summary>
<div style='color:#8b949e;font-size:.78rem;line-height:1.7;margin-top:4px'>
  <b>Critérios de selecção</b> (derivados da calibração do backtest):<br>
  Over 2.5: prob ≥ 60% · BTTS: prob ≥ 60% · 1X2: prob ≥ 55% (apenas ALTA/MÉDIA)<br>
  Abaixo destes limiares, o EV é negativo no backtest.<br><br>
  <b>Sinal de edge</b>: ✅ Forte — IC inferior acima do break-even (n≥20) ·
  ⚠️ Moderado — EV positivo mas IC largo · ❌ Fraco — EV negativo<br>
  <b>Referência</b>: liga (n≥20) > conf (n≥20) > global · Kelly ¼ só com n≥20<br>
  <b>Break-even</b>: O2.5 52.6% · BTTS 54.1% · 1X2 45.5%<br>
  <b>Score composto</b>: EV real do mercado × peso do edge — define a ordem dos jogos
</div>
</details>

{top_picks_html}

{backtest_table}

{tracker_html}

<h2 style='color:#e6edf3;font-size:1rem;margin:20px 0 12px'>
  Jogos de Hoje — {total_games} com picks
  {'<span style="color:#3fb950;margin-left:8px">' + str(strong_picks) + ' fortes</span>' if strong_picks else ''}
</h2>

{games_html}

<p style='text-align:center;color:#6e7681;font-size:.75rem;margin-top:20px'>
  Analista · Limiares e edge derivados do backtest do Matemática Da Bola · nunovinhas-creator/Analista
</p>
</body>
</html>"""

    with open(f"{DOCS_DIR}/today_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("[dashboard] today_dashboard.html gerado")
