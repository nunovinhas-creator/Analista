# emailer.py — Envia relatório diário por email via Gmail SMTP
import os
import smtplib
import re
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENT = "nunovinhas@gmail.com"
PAGES_BASE = "https://nunovinhas-creator.github.io/Analista"


def _pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def _c(v, threshold=0.0):
    return "#27ae60" if v >= threshold else "#e74c3c"


def _kpi_cell(label, value, color="#27ae60"):
    return f"""
    <td style="padding:12px 16px;text-align:center;border-right:1px solid #eee;">
      <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.04em;">{label}</div>
      <div style="font-size:1.4rem;font-weight:700;color:{color};margin-top:4px;">{value}</div>
    </td>"""


def _market_table_row(name, s):
    if s.get("picks", 0) == 0:
        return ""
    wrc = _c(s["win_rate"], 0.52)
    rc  = _c(s.get("roi", 0))
    return (
        f"<tr>"
        f"<td style='padding:6px 10px'><b>{name}</b></td>"
        f"<td style='padding:6px 10px'>{s['picks']}</td>"
        f"<td style='padding:6px 10px;color:{wrc}'>{_pct(s['win_rate'])}</td>"
        f"<td style='padding:6px 10px;color:{rc}'>{s.get('roi',0):+.1f}u ({s.get('roi_pct',0):+.1f}%)</td>"
        f"</tr>"
    )


def _md_to_html(text: str) -> str:
    """Conversão mínima de Markdown para HTML para o email."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            lines.append(f"<h3 style='color:#2c3e50;margin:18px 0 6px;font-size:1rem'>{stripped[3:]}</h3>")
        elif stripped.startswith("- "):
            lines.append(f"<li style='margin-bottom:4px'>{stripped[2:]}</li>")
        elif stripped.startswith("**") and stripped.endswith("**"):
            lines.append(f"<p><b>{stripped[2:-2]}</b></p>")
        elif stripped:
            lines.append(f"<p style='margin:4px 0'>{stripped}</p>")
        else:
            lines.append("<br>")
    return "\n".join(lines)


def build_html_email(over25_stats: dict, football_stats: dict, ai_report: str) -> str:
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    o   = over25_stats
    f   = football_stats
    pm  = f.get("per_market", {})
    tr  = f.get("trebles", {})
    r7o = o.get("recent_7d", {})
    r7f = f.get("recent_7d", {}).get("per_market", {})

    # KPIs over25
    o_kpis = (
        _kpi_cell("Win Rate", _pct(o.get("win_rate", 0)), _c(o.get("win_rate", 0), .52)) +
        _kpi_cell("ROI Total", f"{o.get('roi', 0):+.2f}u", _c(o.get("roi", 0))) +
        _kpi_cell("Yield", f"{o.get('roi_pct', 0):+.1f}%", _c(o.get("roi_pct", 0))) +
        _kpi_cell("Streak", f"{'+'if o.get('streak_type')=='WIN' else '-'}{o.get('streak',0)}", _c(1 if o.get("streak_type") == "WIN" else -1)) +
        _kpi_cell("WR 7d", _pct(r7o.get("win_rate", 0)), _c(r7o.get("win_rate", 0), .52))
    )

    # KPIs football
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
        _market_table_row("BTTS", pm.get("btts", {})) +
        _market_table_row("1X2", pm.get("1x2", {})) +
        _market_table_row("xG", pm.get("xg", {}))
    )

    ai_html = _md_to_html(ai_report) if ai_report else "<p style='color:#888'>Análise IA não disponível.</p>"

    # Tabela breakdown por movimento (gerada fora do f-string para evitar backslash)
    mov_rows = ""
    for k, v in o.get("by_movement", {}).items():
        if v.get("count", 0) == 0:
            continue
        mc  = _c(v["win_rate"], .52)
        rc  = _c(v.get("roi", 0))
        roi_v = v.get("roi", 0)
        mov_rows += (
            f"<tr><td style='padding:5px 10px'>{k}</td>"
            f"<td style='padding:5px 10px;color:{mc}'>{_pct(v['win_rate'])}</td>"
            f"<td style='padding:5px 10px;color:{rc}'>{roi_v:+.2f}u</td></tr>"
        )

    section_style = "background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;margin-bottom:16px;"
    header_style  = "background:#1a1a2e;color:#58a6ff;padding:20px 24px;border-radius:8px 8px 0 0;margin-bottom:16px;"

    return f"""<!DOCTYPE html>
<html lang="pt">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="background:#f4f5f7;font-family:'Segoe UI',Arial,sans-serif;font-size:14px;color:#333;margin:0;padding:20px;">
<div style="max-width:680px;margin:0 auto;">

  <div style="{header_style}">
    <h1 style="margin:0;font-size:1.4rem;">📊 Analista — Relatório Diário</h1>
    <p style="margin:6px 0 0;color:#8b949e;font-size:.85rem;">{now} · Análise completa dos dois sistemas</p>
  </div>

  <!-- Over 2.5 Scanner -->
  <div style="{section_style}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">🎯 Over 2.5 Scanner</h2>
    <p style="color:#666;font-size:.82rem;margin-bottom:10px;">{o.get('resolved',0)} picks resolvidos · {o.get('pending',0)} pendentes</p>
    <table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-radius:6px;overflow:hidden;">
      <tr style="background:#f8f9fa">{o_kpis}</tr>
    </table>
    <div style="margin-top:14px">
      <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
        <tr style="background:#f8f9fa">
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">Segmento</th>
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">WR</th>
          <th style="padding:6px 10px;text-align:left;border-bottom:1px solid #eee">ROI</th>
        </tr>
        {mov_rows}
      </table>
    </div>
  </div>

  <!-- Football Dashboard -->
  <div style="{section_style}">
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

  <!-- Análise IA -->
  <div style="{section_style}">
    <h2 style="color:#1a1a2e;margin:0 0 14px;font-size:1.1rem;">🤖 Análise Científica</h2>
    <div style="font-size:.85rem;line-height:1.6;color:#333;">
      {ai_html}
    </div>
  </div>

  <!-- Links dashboards -->
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

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
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
