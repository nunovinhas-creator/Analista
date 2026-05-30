# emailer.py — Envia relatório diário por email via Gmail SMTP
import html as _html
import os
import re
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENT  = "nunovinhas@gmail.com"
PAGES_BASE = "https://nunovinhas-creator.github.io/Analista"


def _pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def _c(v, threshold=0.0):
    return "#27ae60" if v >= threshold else "#e74c3c"


def _kpi_cell(label, value, color="#27ae60"):
    return (
        f"<td style='padding:12px 16px;text-align:center;border-right:1px solid #eee;'>"
        f"<div style='font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;'>{label}</div>"
        f"<div style='font-size:1.4rem;font-weight:700;color:{color};margin-top:4px;'>{value}</div>"
        f"</td>"
    )


def _market_table_row(name, s):
    if s.get("picks", 0) == 0:
        return ""
    reliable = s.get("reliable", True)
    row_s    = "opacity:.65;font-style:italic" if not reliable else ""
    warn     = " ⚠" if not reliable else ""
    wrc = _c(s["win_rate"], 0.52)
    rc  = _c(s.get("roi", 0))
    ci_l, ci_h = s.get("ci_low", 0), s.get("ci_high", 1)
    return (
        f"<tr style='{row_s}'>"
        f"<td style='padding:6px 10px'><b>{name}</b>{warn}</td>"
        f"<td style='padding:6px 10px'>{s['picks']}</td>"
        f"<td style='padding:6px 10px;color:{wrc}'>{_pct(s['win_rate'])}"
        f" <span style='font-size:.78rem;color:#999'>[{ci_l:.0%}–{ci_h:.0%}]</span></td>"
        f"<td style='padding:6px 10px;color:{rc}'>{s.get('roi',0):+.1f}u ({s.get('roi_pct',0):+.1f}%)</td>"
        f"</tr>"
    )


def _md_to_html(text: str) -> str:
    def _inline(s):
        s = _html.escape(s)
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        return s

    lines_out = []
    in_list = False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("### "):
            if in_list:
                lines_out.append("</ul>")
                in_list = False
            lines_out.append(f"<h4 style='color:#2c3e50;margin:16px 0 6px;font-size:.95rem'>{_inline(s[4:])}</h4>")
        elif s.startswith("## "):
            if in_list:
                lines_out.append("</ul>")
                in_list = False
            lines_out.append(f"<h3 style='color:#2c3e50;margin:18px 0 6px;font-size:1rem'>{_inline(s[3:])}</h3>")
        elif s.startswith("- "):
            if not in_list:
                lines_out.append("<ul style='margin:4px 0;padding-left:20px'>")
                in_list = True
            lines_out.append(f"<li style='margin-bottom:4px'>{_inline(s[2:])}</li>")
        elif s:
            if in_list:
                lines_out.append("</ul>")
                in_list = False
            lines_out.append(f"<p style='margin:4px 0'>{_inline(s)}</p>")
        else:
            if in_list:
                lines_out.append("</ul>")
                in_list = False
            lines_out.append("<br>")
    if in_list:
        lines_out.append("</ul>")
    return "\n".join(lines_out)


def build_html_email(over25_stats: dict, football_stats: dict, ai_report: str) -> str:
    now  = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    o    = over25_stats
    f    = football_stats
    pm   = f.get("per_market", {})
    tr   = f.get("trebles", {})
    r7o  = o.get("recent_7d", {})
    clv  = o.get("avg_clv")
    max_dd = o.get("max_drawdown", 0)

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
    ci_low_o = o.get("ci_low", 0)
    ci_hi_o  = o.get("ci_high", 1)
    dd_color = "#27ae60" if max_dd == 0 else ("#e67e22" if max_dd < 5 else "#e74c3c")
    o_kpis = (
        _kpi_cell("Win Rate", f"{_pct(o.get('win_rate',0))}<div style='font-size:.7rem;color:#aaa'>[{ci_low_o:.0%}–{ci_hi_o:.0%}]</div>", _c(o.get("win_rate", 0), .52)) +
        _kpi_cell("ROI Total", f"{o.get('roi', 0):+.2f}u", _c(o.get("roi", 0))) +
        _kpi_cell("Yield", f"{o.get('roi_pct', 0):+.1f}%", _c(o.get("roi_pct", 0))) +
        _kpi_cell("Max DD", f"-{max_dd:.2f}u", dd_color) +
        _kpi_cell("WR 7d", _pct(r7o.get("win_rate", 0)), _c(r7o.get("win_rate", 0), .52))
    )

    # KPIs Football
    f_kpis = (
        _kpi_cell("O2.5 WR", _pct(pm.get("o25", {}).get("win_rate", 0)), _c(pm.get("o25", {}).get("win_rate", 0), .52)) +
        _kpi_cell("BTTS WR", _pct(pm.get("btts", {}).get("win_rate", 0)), _c(pm.get("btts", {}).get("win_rate", 0), .55)) +
        _kpi_cell("1X2 WR", _pct(pm.get("1x2", {}).get("win_rate", 0)), _c(pm.get("1x2", {}).get("win_rate", 0), .52)) +
        _kpi_cell("Triplas WR", _pct(tr.get("win_rate", 0)), _c(tr.get("win_rate", 0), .30)) +
        _kpi_cell("Triplas ROI", f"{tr.get('roi', 0):+.1f}u", _c(tr.get("roi", 0)))
    )

    # Tabela de mercados football
    fm_rows = (
        _market_table_row("Over 2.5", pm.get("o25", {})) +
        _market_table_row("BTTS",     pm.get("btts", {})) +
        _market_table_row("1X2",      pm.get("1x2", {})) +
        _market_table_row("xG",       pm.get("xg", {}))
    )

    # Tabela breakdown Over 2.5 (movimento)
    mov_rows = ""
    for mv, v in o.get("by_movement", {}).items():
        if v.get("count", 0) == 0:
            continue
        reliable = v.get("reliable", True)
        row_s    = "opacity:.65;font-style:italic" if not reliable else ""
        mc   = _c(v["win_rate"], .52)
        rc   = _c(v.get("roi", 0))
        ci_l, ci_h = v.get("ci_low", 0), v.get("ci_high", 1)
        mov_rows += (
            f"<tr style='{row_s}'><td style='padding:5px 10px'>{mv}</td>"
            f"<td style='padding:5px 10px;color:{mc}'>{_pct(v['win_rate'])}"
            f" <span style='font-size:.78rem;color:#999'>[{ci_l:.0%}–{ci_h:.0%}]</span></td>"
            f"<td style='padding:5px 10px;color:{rc}'>{v.get('roi', 0):+.2f}u</td></tr>"
        )

    # Picks pendentes com Kelly
    pending_kelly_rows = ""
    for p in o.get("pending_with_kelly", []):
        odds_s = f"{p['odds']:.2f}x" if p["odds"] else "—"
        if p["kelly_ok"]:
            stake_cell = f"<b style='color:#27ae60'>{p['kelly_pct']:.1f}% banca</b>"
            if p.get("kelly_note"):
                stake_cell += f"<br><span style='font-size:.75rem;color:#e67e22'>{_html.escape(p['kelly_note'])}</span>"
        else:
            stake_cell = f"<span style='color:#888;font-size:.82rem'>{_html.escape(p.get('kelly_note', '—'))}</span>"
        pending_kelly_rows += (
            f"<tr><td style='padding:5px 8px'><b>{_html.escape(p['casa'])}</b> vs {_html.escape(p['fora'])}</td>"
            f"<td style='padding:5px 8px'>{odds_s}</td>"
            f"<td style='padding:5px 8px'>{p['score']:.0f}</td>"
            f"<td style='padding:5px 8px'>{p['xg']:.1f}</td>"
            f"<td style='padding:5px 8px'>{_html.escape(p['movimento'])}</td>"
            f"<td style='padding:5px 8px'>{stake_cell}</td></tr>"
        )

    _ss = "background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;margin-bottom:16px;"
    pending_section = ""
    if pending_kelly_rows:
        pending_section = f"""
  <div style="{_ss}">
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
      {pending_kelly_rows}
    </table>
  </div>"""

    ai_html = _md_to_html(ai_report) if ai_report else "<p style='color:#888'>Análise não disponível.</p>"

    SECTION_S = "background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;margin-bottom:16px;"
    header_s  = "background:#1a1a2e;color:#58a6ff;padding:20px 24px;border-radius:8px 8px 0 0;margin-bottom:16px;"

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
    <p style="color:#666;font-size:.82rem;margin-bottom:10px;">{o.get('resolved',0)} picks resolvidos · {o.get('pending',0)} pendentes</p>
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
        {mov_rows}
      </table>
    </div>
  </div>

  {pending_section}

  <!-- Football Dashboard -->
  <div style="{SECTION_S}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">⚽ Matemática Da Bola</h2>
    <p style="color:#666;font-size:.82rem;margin-bottom:10px;">{f.get('total',0)} registos · {f.get('dates_processed',0)} dias processados</p>
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
  </div>

  <p style="text-align:center;color:#aaa;font-size:.78rem;margin-top:10px;">
    Analista · Relatório automático · nunovinhas-creator/Analista
  </p>
</div>
</body>
</html>"""


def send_daily_report(over25_stats: dict, football_stats: dict, ai_report: str):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_pass:
        print("[WARN] GMAIL_USER ou GMAIL_APP_PASSWORD não definidos — email não enviado")
        return

    now     = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    subject = f"📊 Analista — Relatório Diário {now}"
    html_body = build_html_email(over25_stats, football_stats, ai_report)

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
