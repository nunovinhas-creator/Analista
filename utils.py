# utils.py — utilitários partilhados entre todos os módulos do Analista
import html as _html
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MARKET_BASE_ODDS = {"o25": 1.90, "btts": 1.85, "1x2": 2.20}
MARKET_LABELS    = {"o25": "Over 2.5", "btts": "BTTS", "1x2": "1X2"}

_LISBON_TZ = ZoneInfo("Europe/Lisbon")


def now_lisbon():
    """Devolve datetime actual no fuso Europe/Lisbon (WEST/WET — imune a UTC drift)."""
    return datetime.now(_LISBON_TZ)

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


def wilson_ci(wins, n, z=1.96):
    """Intervalo de confiança Wilson 95%."""
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z * (p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def segment_stats(records, pick_key, hit_key):
    """Calcula win rate, CI e ROI para um segmento de picks/resultados."""
    picks = [r for r in records if r.get(pick_key) and r.get(hit_key) is not None]
    wins  = sum(1 for r in picks if r.get(hit_key))
    n, k  = len(picks), wins
    roi   = k - (n - k)
    ci_low, ci_high = wilson_ci(k, n)
    return {
        "n":        n,
        "picks":    n,   # alias para compatibilidade com dashboard_football e emailer
        "wins":     k,
        "win_rate": k / n if n else 0.0,
        "ci_low":   ci_low,
        "ci_high":  ci_high,
        "reliable": n >= 20,
        "roi":      roi,
        "roi_pct":  (roi / n * 100) if n else 0.0,
    }


def safe_float(value, default=0.0):
    """Converte valor para float com fallback silencioso."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def normalize_str(s):
    """Normaliza string para comparação: strip + lower."""
    return (s or "").strip().lower()


def markdown_to_html(text):
    """Converte Markdown simples para HTML (negrito, listas, headings)."""
    import html as _html_mod
    import re as _re

    def _inline(s):
        s = _html_mod.escape(s)
        s = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        return s

    lines_out = []
    in_ul = in_ol = False

    def _close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            lines_out.append("</ul>")
            in_ul = False
        if in_ol:
            lines_out.append("</ol>")
            in_ol = False

    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("### "):
            _close_lists()
            lines_out.append(f"<h4 style='color:#2c3e50;margin:16px 0 6px;font-size:.95rem'>{_inline(s[4:])}</h4>")
        elif s.startswith("## "):
            _close_lists()
            lines_out.append(f"<h3 style='color:#2c3e50;margin:18px 0 6px;font-size:1rem'>{_inline(s[3:])}</h3>")
        elif s.startswith("- "):
            if in_ol:
                lines_out.append("</ol>")
                in_ol = False
            if not in_ul:
                lines_out.append("<ul style='margin:4px 0;padding-left:20px'>")
                in_ul = True
            lines_out.append(f"<li style='margin-bottom:4px'>{_inline(s[2:])}</li>")
        elif _re.match(r'^\d+\.\s', s):
            if in_ul:
                lines_out.append("</ul>")
                in_ul = False
            if not in_ol:
                lines_out.append("<ol style='margin:4px 0;padding-left:20px'>")
                in_ol = True
            item = _re.sub(r'^\d+\.\s+', '', s)
            lines_out.append(f"<li style='margin-bottom:4px'>{_inline(item)}</li>")
        elif s:
            _close_lists()
            lines_out.append(f"<p style='margin:4px 0'>{_inline(s)}</p>")
        else:
            _close_lists()
            lines_out.append("<br>")
    _close_lists()
    return "\n".join(lines_out)


def parse_date(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def kelly_quarter(wr, odds, cap=3.0):
    """¼ Kelly como percentagem da banca, com tecto."""
    if odds <= 1.01 or wr <= 0:
        return 0.0
    b = odds - 1
    return round(min(max((wr * b - (1 - wr)) / b / 4, 0.0) * 100, cap), 1)


def pct(v, d=1):
    if v is None:
        return "—"
    return f"{v * 100:.{d}f}%"


def color(v, threshold=0.0):
    if v is None:
        return "oklch(63% 0.024 82)"
    return "oklch(70% 0.12 188)" if v >= threshold else "oklch(58% 0.15 35)"


def escape(s):
    """Escapa string para uso seguro em HTML."""
    return _html.escape(str(s)) if s else ""
