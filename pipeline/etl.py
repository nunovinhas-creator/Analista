# etl.py — Pipeline ETL: fetch → validate → transform → cache
import sys
import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

# Garante que o root do projecto está no sys.path para importar fetcher e schemas
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fetcher import fetch_all_data
from data.schema.picks_schema import validate_picks
from data.schema.history_schema import validate_history
from pipeline.transformer import (
    normalize_pick,
    normalize_history_record,
)

_DEFAULT_CACHE_PATH = os.path.join(_PROJECT_ROOT, "docs", "etl_cache.json")
_CACHE_MAX_AGE_HOURS = 2


@dataclass
class ETLResult:
    """Resultado de uma execução do pipeline ETL."""
    raw_data: dict = field(default_factory=dict)
    validated: bool = False
    validation_errors: list = field(default_factory=list)
    transformed_data: dict = field(default_factory=dict)
    run_at: str = ""
    duration_seconds: float = 0.0


def transform_picks(picks_list):
    """Normaliza lista de picks: coerce tipos, preenche None para numéricos em falta.

    Retorna nova lista de dicts normalizados.
    """
    if not picks_list:
        return []
    return [normalize_pick(p) for p in picks_list]


def transform_history(history_dict):
    """Normaliza history_dict: garante floats nos campos numéricos e ordena por data.

    Retorna novo dict com 'records' normalizados e ordenados.
    """
    if not isinstance(history_dict, dict):
        return {"records": []}

    records = history_dict.get("records", [])
    normalized = [normalize_history_record(r) for r in records]

    # Ordena por data (YYYY-MM-DD string sort é suficiente para formato ISO)
    def _sort_key(r):
        d = r.get("date")
        if isinstance(d, str):
            return d
        return ""

    normalized_sorted = sorted(normalized, key=_sort_key)

    result = dict(history_dict)  # preserva outros campos (dates_processed, etc.)
    result["records"] = normalized_sorted
    return result


def run_etl(validate=True, transform=True):
    """Executa o pipeline ETL completo.

    1. Fetch de dados externos via fetcher.fetch_all_data()
    2. Validação opcional com pandera schemas
    3. Transformação opcional com normalize_*
    4. Retorna ETLResult com todos os metadados

    Parâmetros:
        validate (bool): se True, corre validação Pandera
        transform (bool): se True, normaliza os dados

    Retorna:
        ETLResult
    """
    start = datetime.now(timezone.utc)
    result = ETLResult(run_at=start.isoformat())

    # --- 1. Fetch ---
    try:
        raw = fetch_all_data()
        result.raw_data = raw
    except Exception as e:
        result.validation_errors.append(f"Fetch falhou: {e}")
        result.duration_seconds = (datetime.now(timezone.utc) - start).total_seconds()
        return result

    picks = raw.get("over25_picks", [])
    history = raw.get("football_history", {"records": []})

    all_errors = []

    # --- 2. Validação ---
    if validate:
        picks_valid, picks_errors, _ = validate_picks(picks)
        if not picks_valid:
            all_errors.extend([f"[picks] {e}" for e in picks_errors])

        hist_valid, hist_errors, _ = validate_history(history)
        if not hist_valid:
            all_errors.extend([f"[history] {e}" for e in hist_errors])

        result.validated = len(all_errors) == 0
        result.validation_errors = all_errors
    else:
        result.validated = True

    # --- 3. Transformação ---
    if transform:
        transformed_picks = transform_picks(picks)
        transformed_history = transform_history(history)
        result.transformed_data = {
            "over25_picks": transformed_picks,
            "football_history": transformed_history,
            "over25_picks_1x2": raw.get("over25_picks_1x2", []),
            "football_trebles": raw.get("football_trebles", {}),
            "fetched_at": raw.get("fetched_at", start.isoformat()),
        }
    else:
        result.transformed_data = {
            "over25_picks": picks,
            "football_history": history,
            "over25_picks_1x2": raw.get("over25_picks_1x2", []),
            "football_trebles": raw.get("football_trebles", {}),
            "fetched_at": raw.get("fetched_at", start.isoformat()),
        }

    result.duration_seconds = (datetime.now(timezone.utc) - start).total_seconds()
    return result


def get_data_summary(etl_result):
    """Extrai sumário de alto nível do ETLResult.

    Retorna dict com n_picks, n_history_records, n_picks_resolved,
    date_range, leagues, last_fetch_at.
    """
    td = etl_result.transformed_data or {}
    picks = td.get("over25_picks", [])
    history = td.get("football_history", {})
    records = history.get("records", []) if isinstance(history, dict) else []

    n_picks = len(picks)
    n_history = len(records)

    # Picks resolvidos
    n_resolved = sum(
        1 for p in picks
        if isinstance(p, dict) and p.get("result_over25") in ("WIN", "LOSS")
    )

    # Intervalo de datas dos picks
    dates_picks = []
    for p in picks:
        if isinstance(p, dict) and p.get("data"):
            try:
                d = str(p["data"])[:10]
                dates_picks.append(d)
            except Exception:
                pass

    date_range = {"min_date": None, "max_date": None}
    if dates_picks:
        sorted_dates = sorted(dates_picks)
        date_range = {"min_date": sorted_dates[0], "max_date": sorted_dates[-1]}

    # Ligas distintas (picks + history)
    leagues = set()
    for p in picks:
        if isinstance(p, dict) and p.get("liga"):
            leagues.add(p["liga"])
    for r in records:
        if isinstance(r, dict) and r.get("league"):
            leagues.add(r["league"])

    return {
        "n_picks": n_picks,
        "n_history_records": n_history,
        "n_picks_resolved": n_resolved,
        "date_range": date_range,
        "leagues": sorted(leagues),
        "last_fetch_at": td.get("fetched_at", etl_result.run_at),
    }


def cache_to_json(etl_result, path=None):
    """Guarda transformed_data em JSON para cache local.

    Cria o directório docs/ se não existir.
    """
    if path is None:
        path = _DEFAULT_CACHE_PATH

    os.makedirs(os.path.dirname(path), exist_ok=True)

    payload = {
        "cached_at": etl_result.run_at,
        "validated": etl_result.validated,
        "validation_errors": etl_result.validation_errors,
        "duration_seconds": etl_result.duration_seconds,
        "data": etl_result.transformed_data,
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str, indent=2)
        print(f"[etl] cache guardado em {path}")
    except Exception as e:
        print(f"[WARN] cache_to_json falhou: {e}")


def load_from_cache(path=None):
    """Carrega dados do cache JSON se existir e tiver menos de 2 horas.

    Retorna dict com os dados ou None se cache inválido/expirado.
    """
    if path is None:
        path = _DEFAULT_CACHE_PATH

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"[WARN] load_from_cache falhou a ler: {e}")
        return None

    cached_at_str = payload.get("cached_at")
    if not cached_at_str:
        return None

    try:
        # Suporta datetime com ou sem timezone
        cached_at = datetime.fromisoformat(cached_at_str)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - cached_at
        if age > timedelta(hours=_CACHE_MAX_AGE_HOURS):
            print(f"[etl] cache expirado (idade: {age})")
            return None
    except Exception as e:
        print(f"[WARN] load_from_cache data inválida: {e}")
        return None

    return payload.get("data")
