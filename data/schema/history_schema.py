# history_schema.py — Validação Pandera para football history
import pandas as pd
import pandera as pa
from pandera import Column, Check, DataFrameSchema


# Schema Pandera para os registos do football-dashboard history.json
HISTORY_SCHEMA = DataFrameSchema(
    columns={
        "date": Column(
            str,
            checks=Check.str_matches(r"^\d{4}-\d{2}-\d{2}$"),
            nullable=False,
        ),
        "home": Column(str, nullable=False),
        "away": Column(str, nullable=False),
        "league": Column(str, nullable=True),
        "hw": Column(
            float,
            checks=Check.in_range(0, 100),
            nullable=False,
            coerce=True,
        ),
        "dr": Column(
            float,
            checks=Check.in_range(0, 100),
            nullable=False,
            coerce=True,
        ),
        "aw": Column(
            float,
            checks=Check.in_range(0, 100),
            nullable=False,
            coerce=True,
        ),
        "po": Column(
            float,
            checks=Check.in_range(0, 100),
            nullable=False,
            coerce=True,
        ),
        "pb": Column(
            float,
            checks=Check.in_range(0, 100),
            nullable=False,
            coerce=True,
        ),
        "conf": Column(
            str,
            checks=Check.isin(["ALTA", "MÉDIA", "BAIXA"]),
            nullable=True,
        ),
        "pick_o25": Column(nullable=True),
        "hit_o25":  Column(nullable=True),
    },
    strict=False,  # permite colunas extra (pick_1x2, hit_1x2, etc.)
)


def validate_history(history_dict):
    """Valida dicionário history contra o schema Pandera.

    Retorna tuplo (is_valid: bool, errors: list[str], n_records: int).
    """
    if not isinstance(history_dict, dict):
        return (False, ["history_dict não é um dicionário"], 0)

    records = history_dict.get("records", [])
    n = len(records)

    if not records:
        return (True, [], 0)

    try:
        df = pd.DataFrame(records)
    except Exception as e:
        return (False, [f"Falha a construir DataFrame: {e}"], n)

    # Converte campos bool para bool/None explicitamente
    for bool_col in ("pick_o25", "hit_o25", "pick_1x2", "hit_1x2", "pick_btts", "hit_btts"):
        if bool_col in df.columns:
            df[bool_col] = df[bool_col].apply(
                lambda v: bool(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
            )

    try:
        HISTORY_SCHEMA.validate(df, lazy=True)
        return (True, [], n)
    except pa.errors.SchemaErrors as exc:
        errors = []
        for _, row in exc.failure_cases.iterrows():
            col = row.get("column", "?")
            case = row.get("failure_case", "?")
            check = row.get("check", "?")
            errors.append(f"Coluna '{col}': check '{check}' falhou para valor '{case}'")
        return (False, errors, n)
    except pa.errors.SchemaError as exc:
        return (False, [str(exc)], n)
    except Exception as exc:
        return (False, [f"Erro inesperado: {exc}"], n)


def history_quality_report(history_dict):
    """Relatório de qualidade do history sem levantar excepções de validação.

    Retorna dict com métricas de completude e qualidade.
    """
    if not isinstance(history_dict, dict):
        return {
            "n_records": 0,
            "n_dates": 0,
            "leagues_count": {},
            "avg_hw": None,
            "avg_dr": None,
            "avg_aw": None,
            "completeness": {},
            "date_range": {"min_date": None, "max_date": None},
        }

    records = history_dict.get("records", [])
    n_records = len(records)

    if not records:
        return {
            "n_records": 0,
            "n_dates": 0,
            "leagues_count": {},
            "avg_hw": None,
            "avg_dr": None,
            "avg_aw": None,
            "completeness": {},
            "date_range": {"min_date": None, "max_date": None},
        }

    df = pd.DataFrame(records)

    # Datas únicas
    dates = df["date"].dropna().unique().tolist() if "date" in df.columns else []
    n_dates = len(dates)

    # Contagem por liga
    leagues_count = {}
    if "league" in df.columns:
        leagues_count = df["league"].value_counts().to_dict()

    # Médias das probabilidades
    def safe_mean(col):
        if col not in df.columns:
            return None
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        return round(float(vals.mean()), 2) if len(vals) > 0 else None

    avg_hw = safe_mean("hw")
    avg_dr = safe_mean("dr")
    avg_aw = safe_mean("aw")

    # Completude: percentagem de campos preenchidos
    key_fields = ["date", "home", "away", "league", "hw", "dr", "aw", "po", "pb", "conf",
                  "pick_1x2", "hit_1x2", "pick_o25", "hit_o25", "pick_btts", "hit_btts"]
    completeness = {}
    for field in key_fields:
        if field in df.columns:
            filled = df[field].notna().sum()
            completeness[field] = round(float(filled) / n_records * 100, 1)
        else:
            completeness[field] = 0.0

    # Intervalo de datas
    min_date = None
    max_date = None
    if dates:
        sorted_dates = sorted(d for d in dates if isinstance(d, str))
        if sorted_dates:
            min_date = sorted_dates[0]
            max_date = sorted_dates[-1]

    return {
        "n_records": n_records,
        "n_dates": n_dates,
        "leagues_count": leagues_count,
        "avg_hw": avg_hw,
        "avg_dr": avg_dr,
        "avg_aw": avg_aw,
        "completeness": completeness,
        "date_range": {"min_date": min_date, "max_date": max_date},
    }
