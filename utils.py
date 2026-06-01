# utils.py — utilitários partilhados entre todos os módulos do Analista
import html as _html
import os
from datetime import datetime, timezone

MARKET_BASE_ODDS = {"o25": 1.90, "btts": 1.85, "1x2": 2.20}
MARKET_LABELS    = {"o25": "Over 2.5", "btts": "BTTS", "1x2": "1X2"}

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
    return f"{v * 100:.{d}f}%"


def color(v, threshold=0.0):
    return "#27ae60" if v >= threshold else "#e74c3c"


def escape(s):
    """Escapa string para uso seguro em HTML."""
    return _html.escape(str(s)) if s else ""
