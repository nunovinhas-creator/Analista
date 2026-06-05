# transformer.py — Utilitários de transformação de dados
import pandas as pd
from datetime import datetime


def normalize_pick(p):
    """Normaliza um registo de pick: coerce numéricos, strip strings, normaliza resultado.

    Retorna novo dict com todos os campos normalizados.
    """
    if not isinstance(p, dict):
        return {}

    def _to_float(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def _strip(v):
        if isinstance(v, str):
            return v.strip()
        return v

    result_raw = p.get("result_over25")
    if result_raw in ("WIN", "LOSS"):
        resultado = result_raw
    elif result_raw in (None, "", "null"):
        resultado = None
    else:
        resultado = None

    clv_raw = p.get("clv")
    # clv pode ser string "null" em alguns registos
    if clv_raw == "null":
        clv_raw = None

    return {
        "data": _strip(p.get("data")),
        "casa": _strip(p.get("casa")),
        "fora": _strip(p.get("fora")),
        "liga": _strip(p.get("liga")),
        "odds_over": _to_float(p.get("odds_over")),
        "movimento": _strip(p.get("movimento")),
        "xg_total": _to_float(p.get("xg_total")),
        "btts_prob": _to_float(p.get("btts_prob")),
        "score_sistema": _to_float(p.get("score_sistema")),
        "result_over25": resultado,
        "clv": _to_float(clv_raw),
    }


def normalize_history_record(r):
    """Normaliza um registo de history: float para hw/dr/aw/po/pb, bool/None para campos hit.

    Retorna novo dict normalizado.
    """
    if not isinstance(r, dict):
        return {}

    def _to_float(v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def _to_bool(v):
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, float) and pd.isna(v):
            return None
        try:
            return bool(v)
        except Exception:
            return None

    return {
        "date": r.get("date"),
        "league": r.get("league"),
        "home": r.get("home"),
        "away": r.get("away"),
        "hw": _to_float(r.get("hw")),
        "dr": _to_float(r.get("dr")),
        "aw": _to_float(r.get("aw")),
        "po": _to_float(r.get("po")),
        "pb": _to_float(r.get("pb")),
        "xg_home": _to_float(r.get("xg_home")),
        "xg_away": _to_float(r.get("xg_away")),
        "conf": r.get("conf"),
        "pick_1x2": _to_bool(r.get("pick_1x2")),
        "hit_1x2": _to_bool(r.get("hit_1x2")),
        "pick_o25": _to_bool(r.get("pick_o25")),
        "hit_o25": _to_bool(r.get("hit_o25")),
        "pick_btts": _to_bool(r.get("pick_btts")),
        "hit_btts": _to_bool(r.get("hit_btts")),
    }


def picks_to_dataframe(picks_list):
    """Converte lista de picks para DataFrame com dtypes correctos.

    Aplica normalize_pick a cada registo antes de construir o DataFrame.
    """
    if not picks_list:
        return pd.DataFrame(columns=[
            "data", "casa", "fora", "liga", "odds_over", "movimento",
            "xg_total", "btts_prob", "score_sistema", "result_over25", "clv",
        ])

    normalized = [normalize_pick(p) for p in picks_list]
    df = pd.DataFrame(normalized)

    # Coerce tipos numéricos
    for col in ("odds_over", "xg_total", "btts_prob", "score_sistema", "clv"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Strings
    for col in ("data", "casa", "fora", "liga", "movimento", "result_over25"):
        if col in df.columns:
            df[col] = df[col].astype("object")

    return df


def history_to_dataframe(records):
    """Converte lista de registos de history para DataFrame.

    Normaliza cada registo e converte coluna 'date' para datetime.
    """
    if not records:
        return pd.DataFrame(columns=[
            "date", "league", "home", "away", "hw", "dr", "aw",
            "po", "pb", "xg_home", "xg_away", "conf",
            "pick_1x2", "hit_1x2", "pick_o25", "hit_o25", "pick_btts", "hit_btts",
        ])

    normalized = [normalize_history_record(r) for r in records]
    df = pd.DataFrame(normalized)

    # Converte coluna date para datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")

    # Coerce numéricos
    for col in ("hw", "dr", "aw", "po", "pb", "xg_home", "xg_away"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def compute_rolling_stats(df, window=20):
    """Adiciona colunas rolling_wr e rolling_roi ao DataFrame de picks.

    Calcula sobre os últimos `window` picks resolvidos (WIN/LOSS).
    Retorna DataFrame com novas colunas (NaN para linhas sem resultado).
    """
    df = df.copy()

    if "result_over25" not in df.columns:
        df["rolling_wr"] = float("nan")
        df["rolling_roi"] = float("nan")
        return df

    # Cria colunas auxiliares apenas para linhas resolvidas
    resolved_mask = df["result_over25"].isin(["WIN", "LOSS"])
    df["_win"] = None
    df["_roi"] = None

    if resolved_mask.any():
        df.loc[resolved_mask, "_win"] = (df.loc[resolved_mask, "result_over25"] == "WIN").astype(float)

        # ROI por pick: (odds - 1) se WIN, -1 se LOSS
        if "odds_over" in df.columns:
            odds = pd.to_numeric(df.loc[resolved_mask, "odds_over"], errors="coerce").fillna(1.0)
            df.loc[resolved_mask, "_roi"] = df.loc[resolved_mask, "_win"] * (odds - 1) + (
                (1 - df.loc[resolved_mask, "_win"]) * -1
            )
        else:
            df.loc[resolved_mask, "_roi"] = df.loc[resolved_mask, "_win"] * 0.85 - (
                1 - df.loc[resolved_mask, "_win"]
            )

    df["_win"] = pd.to_numeric(df["_win"], errors="coerce")
    df["_roi"] = pd.to_numeric(df["_roi"], errors="coerce")

    df["rolling_wr"] = df["_win"].rolling(window=window, min_periods=1).mean()
    df["rolling_roi"] = df["_roi"].rolling(window=window, min_periods=1).mean()

    df.drop(columns=["_win", "_roi"], inplace=True)

    return df


def filter_resolved(df):
    """Mantém apenas linhas com resultado WIN ou LOSS."""
    if "result_over25" not in df.columns:
        return df.iloc[0:0].copy()
    return df[df["result_over25"].isin(["WIN", "LOSS"])].copy()


def filter_pending(df):
    """Mantém apenas linhas sem resultado (None ou '')."""
    if "result_over25" not in df.columns:
        return df.copy()
    return df[~df["result_over25"].isin(["WIN", "LOSS"])].copy()


def add_calendar_features(df, date_col="date"):
    """Adiciona colunas day_of_week, month, week_of_year ao DataFrame.

    Aceita colunas de data como datetime ou string (ISO).
    """
    df = df.copy()

    if date_col not in df.columns:
        df["day_of_week"] = None
        df["month"] = None
        df["week_of_year"] = None
        return df

    dates = pd.to_datetime(df[date_col], errors="coerce")
    df["day_of_week"] = dates.dt.dayofweek   # 0=Segunda, 6=Domingo
    df["month"] = dates.dt.month
    df["week_of_year"] = dates.dt.isocalendar().week.astype("Int64")

    return df
