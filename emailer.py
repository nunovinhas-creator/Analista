# emailer.py — Envia relatório diário por email via Gmail SMTP
import html as _html
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils import color, pct, markdown_to_html

RECIPIENT  = os.environ.get("EMAIL_RECIPIENT", "nunovinhas@gmail.com")
PAGES_BASE = "https://nunovinhas-creator.github.io/Analista"


def _kpi_cell(label, value, col="#27ae60"):
    return (
        f"<td style='padding:12px 16px;text-align:center;border-right:1px solid #eee;'>"
        f"<div style='font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;'>{label}</div>"
        f"<div style='font-size:1.4rem;font-weight:700;color:{col};margin-top:4px;'>{value}</div>"
        f"</td>"
    )


def _market_table_row(name, s):
    if s.get("picks", 0) == 0:
        return ""
    reliable = s.get("reliable", True)
    row_s    = "opacity:.65;font-style:italic" if not reliable else ""
    warn     = " ⚠" if not reliable else ""
    wrc = color(s["win_rate"], 0.52)
    rc  = color(s.get("roi", 0))
    ci_l, ci_h = s.get("ci_low", 0), s.get("ci_high", 1)
    return (
        f"<tr style='{row_s}'>"
        f"<td style='padding:6px 10px'><b>{name}</b>{warn}</td>"
        f"<td style='padding:6px 10px'>{s['picks']}</td>"
        f"<td style='padding:6px 10px;color:{wrc}'>{pct(s['win_rate'])}"
        f" <span style='font-size:.78rem;color:#999'>[{ci_l:.0%}–{ci_h:.0%}]</span></td>"
        f"<td style='padding:6px 10px;color:{rc}'>{s.get('roi',0):+.1f}u ({s.get('roi_pct',0):+.1f}%)</td>"
        f"</tr>"
    )


def build_html_email(over25_stats: dict, football_stats: dict, ai_report: str, today_stats: dict = None) -> str:
    now        = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    o25        = over25_stats
    fb         = football_stats
    per_market = fb.get("per_market", {})
    trebles    = fb.get("trebles", {})
    r7o        = o25.get("recent_7d", {})
    clv        = o25.get("avg_clv")
    max_dd     = o25.get("max_drawdown", 0)

    # Alerta CLV no topo do email
    clv_banner = ""
    if clv is not None and clv < -1:
        clv_banner = (
            f"<div style='background:#fff3cd;border:1px solid #f85149;border-radius:6px;"
            f"padding:12px 16px;margin-bottom:16px;color:#c0392b;font-size:.85rem;'>"
            f"<b>⚠️ CLV Médio: {clv:+.2f}%</b> — sistema a apostar após o mercado mover. "
            f"Verificar timing das apostas para capturar edge real."
            f"</div>"
        )
    elif clv is not None and clv >= 2:
        clv_banner = (
            f"<div style='background:#d4edda;border:1px solid #27ae60;border-radius:6px;"
            f"padding:12px 16px;margin-bottom:16px;color:#155724;font-size:.85rem;'>"
            f"<b>✅ CLV Médio: {clv:+.2f}%</b> — apostas a ser feitas antes do mercado mover. Edge real confirmado."
            f"</div>"
        )

    # KPIs Over 2.5
    ci_low_o = o25.get("ci_low", 0)
    ci_hi_o  = o25.get("ci_high", 1)
    dd_color = "#27ae60" if max_dd == 0 else ("#e67e22" if max_dd < 5 else "#e74c3c")
    o_kpis = (
        _kpi_cell("Win Rate", f"{pct(o25.get('win_rate',0))}<div style='font-size:.7rem;color:#aaa'>[{ci_low_o:.0%}–{ci_hi_o:.0%}]</div>", color(o25.get("win_rate", 0), .52)) +
        _kpi_cell("ROI Total", f"{o25.get('roi', 0):+.2f}u", color(o25.get("roi", 0))) +
        _kpi_cell("Yield", f"{o25.get('roi_pct', 0):+.1f}%", color(o25.get("roi_pct", 0))) +
        _kpi_cell("Max DD", f"-{max_dd:.2f}u", dd_color) +
        _kpi_cell("WR 7d", pct(r7o.get("win_rate", 0)), color(r7o.get("win_rate", 0), .52))
    )

    # KPIs Football
    f_kpis = (
        _kpi_cell("O2.5 WR", pct(per_market.get("o25", {}).get("win_rate", 0)), color(per_market.get("o25", {}).get("win_rate", 0), .52)) +
        _kpi_cell("BTTS WR", pct(per_market.get("btts", {}).get("win_rate", 0)), color(per_market.get("btts", {}).get("win_rate", 0), .55)) +
        _kpi_cell("1X2 WR", pct(per_market.get("1x2", {}).get("win_rate", 0)), color(per_market.get("1x2", {}).get("win_rate", 0), .52)) +
        _kpi_cell("Triplas WR", pct(trebles.get("win_rate", 0)), color(trebles.get("win_rate", 0), .30)) +
        _kpi_cell("Triplas ROI", f"{trebles.get('roi', 0):+.1f}u", color(trebles.get("roi", 0)))
    )

    # Tabela de mercados football
    fm_rows = (
        _market_table_row("Over 2.5", per_market.get("o25", {})) +
        _market_table_row("BTTS",     per_market.get("btts", {})) +
        _market_table_row("1X2",      per_market.get("1x2", {})) +
        _market_table_row("xG",       per_market.get("xg", {}))
    )

    # Tabela breakdown Over 2.5 (movimento)
    mov_rows = []
    for mv, v in o25.get("by_movement", {}).items():
        if v.get("count", 0) == 0:
            continue
        reliable = v.get("reliable", True)
        row_s    = "opacity:.65;font-style:italic" if not reliable else ""
        mc   = color(v["win_rate"], .52)
        rc   = color(v.get("roi", 0))
        ci_l, ci_h = v.get("ci_low", 0), v.get("ci_high", 1)
        mov_rows.append(
            f"<tr style='{row_s}'><td style='padding:5px 10px'>{mv}</td>"
            f"<td style='padding:5px 10px;color:{mc}'>{pct(v['win_rate'])}"
            f" <span style='font-size:.78rem;color:#999'>[{ci_l:.0%}–{ci_h:.0%}]</span></td>"
            f"<td style='padding:5px 10px;color:{rc}'>{v.get('roi', 0):+.2f}u</td></tr>"
        )
    mov_rows_html = "".join(mov_rows)

    # Picks pendentes com Kelly
    pending_kelly_rows = []
    for p in o25.get("pending_with_kelly", []):
        odds_s = f"{p['odds']:.2f}x" if p["odds"] else "—"
        if p["kelly_ok"]:
            stake_cell = f"<b style='color:#27ae60'>{p['kelly_pct']:.1f}% banca</b>"
            if p.get("kelly_note"):
                stake_cell += f"<br><span style='font-size:.75rem;color:#e67e22'>{_html.escape(p['kelly_note'])}</span>"
        else:
            stake_cell = f"<span style='color:#888;font-size:.82rem'>{_html.escape(p.get('kelly_note', '—'))}</span>"
        pending_kelly_rows.append(
            f"<tr><td style='padding:5px 8px'><b>{_html.escape(p['casa'])}</b> vs {_html.escape(p['fora'])}</td>"
            f"<td style='padding:5px 8px'>{odds_s}</td>"
            f"<td style='padding:5px 8px'>{p['score']:.0f}</td>"
            f"<td style='padding:5px 8px'>{p['xg']:.1f}</td>"
            f"<td style='padding:5px 8px'>{_html.escape(p['movimento'])}</td>"
            f"<td style='padding:5px 8px'>{stake_cell}</td></tr>"
        )
    pending_kelly_html = "".join(pending_kelly_rows)

    SECTION_S = "background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;margin-bottom:16px;"
    pending_section = ""
    if pending_kelly_html:
        pending_section = f"""
  <div style="{SECTION_S}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">⏳ Picks Pendentes — Stakes Kelly</h2>
    <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
      <tr style="background:#f8f9fa">
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #eee">Jogo</th>
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #eee">Odds</th>
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #eee">Score</th>
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #eee">xG</th>
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #eee">Mov.</th>
        <th style="padding:6px 8px;text-align:left;border-bottom:1px solid #eee">Stake ¼ Kelly</th>
      </tr>
      {pending_kelly_html}
    </table>
  </div>"""

    ai_html = markdown_to_html(ai_report) if ai_report else "<p style='color:#888'>Análise não disponível.</p>"

    # Secção Onde Apostar Hoje e Amanhã
    today_section = ""
    if today_stats:
        ts           = today_stats
        today_str    = ts.get("today", "")
        tomorrow_str = ts.get("tomorrow", "")
        all_games    = ts.get("games", [])
        games_today    = [g for g in all_games if g.get("date") == today_str]
        games_tomorrow = [g for g in all_games if g.get("date") == tomorrow_str]

        rows = []
        for date_label, games in [("Hoje", games_today), ("Amanhã", games_tomorrow)]:
            if not games:
                continue
            rows.append(
                f"<tr><td colspan='4' style='padding:7px 10px;background:#f4f5f7;"
                f"font-weight:600;color:#555;font-size:.8rem'>{date_label}</td></tr>"
            )
            for g in games:
                ko_raw = str(g.get("ko_hour", ""))
                ko = (":" in ko_raw and ko_raw or f"{ko_raw}:00") if ko_raw else "—"
                conf = g.get("conf", "")
                if conf == "ALTA":
                    conf_badge = "<span style='background:#1a7f37;color:#fff;border-radius:3px;padding:1px 5px;font-size:.73rem'>ALTA</span>"
                elif conf == "MÉDIA":
                    conf_badge = "<span style='background:#9a6700;color:#fff;border-radius:3px;padding:1px 5px;font-size:.73rem'>MÉDIA</span>"
                else:
                    conf_badge = ""
                picks_html = " &nbsp;·&nbsp; ".join(
                    f"<b style='color:{'#27ae60' if p['edge']=='strong' else '#e67e22'}'>"
                    f"{_html.escape(p['label'])}</b>"
                    f"<span style='color:#999;font-size:.75rem'> {p['edge']}</span>"
                    for p in g.get("picks", [])
                )
                rows.append(
                    f"<tr style='border-bottom:1px solid #f0f0f0'>"
                    f"<td style='padding:6px 10px'>"
                    f"<b>{_html.escape(g['home'])}</b> vs {_html.escape(g['away'])}<br>"
                    f"<span style='font-size:.73rem;color:#888'>{_html.escape(g['league'])}</span></td>"
                    f"<td style='padding:6px 10px;white-space:nowrap'>{ko}</td>"
                    f"<td style='padding:6px 10px'>{conf_badge}</td>"
                    f"<td style='padding:6px 10px;font-size:.82rem'>{picks_html}</td>"
                    f"</tr>"
                )

        if rows:
            rows_html  = "\n".join(rows)
            n_strong   = ts.get("strong_picks", 0)
            total_p    = ts.get("total_picks", 0)
            strong_txt = f" · <b style='color:#27ae60'>{n_strong} fortes</b>" if n_strong else ""
            today_section = f"""
  <div style="{SECTION_S}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">📅 Onde Apostar Hoje e Amanhã</h2>
    <p style="color:#666;font-size:.82rem;margin-bottom:10px;">{ts.get('total_games',0)} jogos · {total_p} picks{strong_txt}</p>
    <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
      <tr style="background:#f8f9fa">
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Jogo</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Hora</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Conf.</th>
        <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Picks</th>
      </tr>
      {rows_html}
    </table>
    <div style="text-align:right;margin-top:12px">
      <a href="{PAGES_BASE}/today_dashboard.html" style="display:inline-block;background:#58a6ff;color:#fff;padding:8px 18px;border-radius:5px;text-decoration:none;font-size:.82rem;font-weight:600">
        Ver Dashboard Completo →
      </a>
    </div>
  </div>"""

    header_s = "background:#1a1a2e;color:#58a6ff;padding:20px 24px;border-radius:8px 8px 0 0;margin-bottom:16px;"

    return f"""<!DOCTYPE html>
<html lang="pt">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="background:#f4f5f7;font-family:'Segoe UI',Arial,sans-serif;font-size:14px;color:#333;margin:0;padding:20px;">
<div style="max-width:700px;margin:0 auto;">

  <div style="{header_s}">
    <h1 style="margin:0;font-size:1.4rem;">📊 Analista — Relatório Diário</h1>
    <p style="margin:6px 0 0;color:#8b949e;font-size:.85rem;">{now} · Análise completa dos dois sistemas</p>
  </div>

  {clv_banner}

  <!-- Over 2.5 Scanner -->
  <div style="{SECTION_S}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">🎯 Over 2.5 Scanner</h2>
    <p style="color:#666;font-size:.82rem;margin-bottom:10px;">{o25.get('resolved',0)} picks resolvidos · {o25.get('pending',0)} pendentes</p>
    <table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-radius:6px;overflow:hidden;">
      <tr style="background:#f8f9fa">{o_kpis}</tr>
    </table>
    <div style="margin-top:14px">
      <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
        <tr style="background:#f8f9fa">
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Movimento</th>
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">WR</th>
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">ROI</th>
        </tr>
        {mov_rows_html}
      </table>
    </div>
  </div>

  {pending_section}

  <!-- Football Dashboard -->
  <div style="{SECTION_S}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">⚽ Matemática Da Bola</h2>
    <p style="color:#666;font-size:.82rem;margin-bottom:10px;">{fb.get('total',0)} registos · {fb.get('dates_processed',0)} dias processados</p>
    <table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-radius:6px;overflow:hidden;">
      <tr style="background:#f8f9fa">{f_kpis}</tr>
    </table>
    <div style="margin-top:14px">
      <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
        <tr style="background:#f8f9fa">
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Mercado</th>
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Picks</th>
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">WR</th>
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">ROI (flat)</th>
        </tr>
        {fm_rows}
      </table>
    </div>
  </div>

  {today_section}

  <!-- Análise Científica -->
  <div style="{SECTION_S}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">🔬 Análise Científica</h2>
    <div style="font-size:.85rem;line-height:1.6;color:#333;">
      {ai_html}
    </div>
  </div>

  <!-- Links -->
  <div style="text-align:center;padding:16px;">
    <a href="{PAGES_BASE}/over25_dashboard.html" style="display:inline-block;background:#58a6ff;color:#fff;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:600;margin:6px;">
      Ver Dashboard Over 2.5
    </a>
    <a href="{PAGES_BASE}/football_dashboard.html" style="display:inline-block;background:#3fb950;color:#fff;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:600;margin:6px;">
      Ver Dashboard Football
    </a>
    <a href="{PAGES_BASE}/today_dashboard.html" style="display:inline-block;background:#f78166;color:#fff;padding:10px 22px;border-radius:6px;text-decoration:none;font-weight:600;margin:6px;">
      Ver Hoje e Amanhã
    </a>
  </div>

  <p style="text-align:center;color:#aaa;font-size:.78rem;margin-top:10px;">
    Analista · Relatório automático · nunovinhas-creator/Analista
  </p>
</div>
</body>
</html>"""


def send_daily_report(over25_stats: dict, football_stats: dict, ai_report: str, today_stats: dict = None):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_pass:
        print("[WARN] GMAIL_USER ou GMAIL_APP_PASSWORD não definidos — email não enviado")
        return

    now     = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    subject = f"📊 Analista — Relatório Diário {now}"
    html_body = build_html_email(over25_stats, football_stats, ai_report, today_stats)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, RECIPIENT, msg.as_string())
        print(f"[email] Relatório enviado para {RECIPIENT}")
    except Exception as e:
        print(f"[ERROR] Falha ao enviar email: {e}")
        raise
