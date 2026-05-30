# fetcher.py — Busca dados dos dois repositórios fonte via raw GitHub URLs
import requests
from datetime import datetime, timezone

OVER25_RAW   = "https://raw.githubusercontent.com/nunovinhas-creator/over25-scanner/main"
FOOTBALL_RAW = "https://raw.githubusercontent.com/nunovinhas-creator/football-dashboard/main"
FOOTBALL_DASHBOARD_HTML_URL = f"{FOOTBALL_RAW}/docs/dashboard.html"


def _get(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_all_data():
    data = {
        "over25_picks": [],
        "over25_picks_1x2": [],
        "football_history": {"records": [], "dates_processed": [], "dates_partial": {}},
        "football_trebles": {"pending": [], "history": []},
        "football_dashboard_html": "",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        fetched = _get(f"{OVER25_RAW}/data/picks.json")
        if not isinstance(fetched, list):
            raise ValueError(f"tipo inesperado: {type(fetched).__name__}")
        data["over25_picks"] = fetched
        print(f"[fetch] over25 picks: {len(data['over25_picks'])} registos")
    except Exception as e:
        print(f"[WARN] over25 picks.json: {e}")

    try:
        fetched = _get(f"{OVER25_RAW}/data/picks_1x2.json")
        if not isinstance(fetched, list):
            raise ValueError(f"tipo inesperado: {type(fetched).__name__}")
        data["over25_picks_1x2"] = fetched
        print(f"[fetch] over25 picks_1x2: {len(data['over25_picks_1x2'])} registos")
    except Exception as e:
        print(f"[WARN] over25 picks_1x2.json: {e}")

    try:
        fetched = _get(f"{FOOTBALL_RAW}/docs/history.json")
        if not isinstance(fetched, dict):
            raise ValueError(f"tipo inesperado: {type(fetched).__name__}")
        data["football_history"] = fetched
        n = len(data["football_history"].get("records", []))
        print(f"[fetch] football history: {n} registos")
    except Exception as e:
        print(f"[WARN] football history.json: {e}")

    try:
        fetched = _get(f"{FOOTBALL_RAW}/docs/trebles.json")
        if not isinstance(fetched, dict):
            raise ValueError(f"tipo inesperado: {type(fetched).__name__}")
        data["football_trebles"] = fetched
        n = len(data["football_trebles"].get("history", []))
        print(f"[fetch] football trebles: {n} histórico")
    except Exception as e:
        print(f"[WARN] football trebles.json: {e}")

    try:
        r = requests.get(FOOTBALL_DASHBOARD_HTML_URL, timeout=20)
        r.raise_for_status()
        data["football_dashboard_html"] = r.text
        print(f"[fetch] football dashboard.html: {len(r.content)} bytes")
    except Exception as e:
        print(f"[WARN] football dashboard.html: {e}")

    return data
