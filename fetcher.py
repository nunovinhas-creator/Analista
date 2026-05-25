# fetcher.py — Busca dados dos dois repositórios fonte via raw GitHub URLs
import requests
from datetime import datetime, timezone

OVER25_RAW = "https://raw.githubusercontent.com/nunovinhas-creator/over25-scanner/main"
FOOTBALL_RAW = "https://raw.githubusercontent.com/nunovinhas-creator/football-dashboard/main"


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
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        data["over25_picks"] = _get(f"{OVER25_RAW}/data/picks.json")
        print(f"[fetch] over25 picks: {len(data['over25_picks'])} registos")
    except Exception as e:
        print(f"[WARN] over25 picks.json: {e}")

    try:
        data["over25_picks_1x2"] = _get(f"{OVER25_RAW}/data/picks_1x2.json")
        print(f"[fetch] over25 picks_1x2: {len(data['over25_picks_1x2'])} registos")
    except Exception as e:
        print(f"[WARN] over25 picks_1x2.json: {e}")

    try:
        data["football_history"] = _get(f"{FOOTBALL_RAW}/docs/history.json")
        n = len(data["football_history"].get("records", []))
        print(f"[fetch] football history: {n} registos")
    except Exception as e:
        print(f"[WARN] football history.json: {e}")

    try:
        data["football_trebles"] = _get(f"{FOOTBALL_RAW}/docs/trebles.json")
        n = len(data["football_trebles"].get("history", []))
        print(f"[fetch] football trebles: {n} histórico")
    except Exception as e:
        print(f"[WARN] football trebles.json: {e}")

    return data
