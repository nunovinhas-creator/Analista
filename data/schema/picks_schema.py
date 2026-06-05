# picks_schema.py — Validação Pandera para picks Over 2.5
import pandas as pd
import pandera as pa
from pandera import Column, Check, DataFrameSchema


# Schema Pandera para os registos de picks Over 2.5
PICKS_SCHEMA = DataFrameSchema(
    columns={
        "data": Column(str, nullable=False),
        "casa": Column(str, nullable=False),
        "fora": Column(str, nullable=False),
        "liga": Column(str, nullable=True),
        "odds_over": Column(
            float,
            checks=[Check(lambda x: (x >= 1.01) & (x <= 50.0), element_wise=True)],
            nullable=True,
            coerce=True,
        ),
        "movimento": Column(
            str,
            checks=Check.isin(["SHORTENING", "DRIFTING"]),
            nullable=True,
        ),
        "xg_total": Column(
            float,
            checks=[Check(lambda x: (x >= 0) & (x <= 20), element_wise=True)],
            nullable=True,
            coerce=True,
        ),
        "btts_prob": Column(
            float,
            checks=[Check(lambda x: (x >= 0) & (x <= 1), element_wise=True)],
            nullable=True,
            coerce=True,
        ),
        "score_sistema": Column(
            float,
            checks=[Check(lambda x: (x >= 0) & (x <= 100), element_wise=True)],
            nullable=True,
            coerce=True,
        ),
        "result_over25": Column(
            str,
            checks=Check.isin(["WIN", "LOSS", ""]),
            nullable=True,
        ),
        "clv": Column(float, nullable=True, coerce=True),
    },
    strict=False,  # permite colunas extra
)


def validate_picks(picks_list):
    """Valida lista de picks contra o schema Pandera.

    Retorna tuplo (is_valid: bool, errors: list[str], n_records: int).
    """
    n = len(picks_list) if picks_list else 0

    if not picks_list:
        return (True, [], 0)

    try:
        df = pd.DataFrame(picks_list)
    except Exception as e:
        return (False, [f"Falha a construir DataFrame: {e}"], n)

    # Normaliza result_over25: None/null -> pd.NA para o schema aceitar nullable
    if "result_over25" in df.columns:
        df["result_over25"] = df["result_over25"].where(
            df["result_over25"].notna(), other=None
        )

    try:
        PICKS_SCHEMA.validate(df, lazy=True)
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


def picks_quality_report(picks_list):
    """Relatório de qualidade dos picks sem levantar excepções de validação.

    Retorna dict com métricas de completude e qualidade.
    """
    if not picks_list:
        return {
            "n_total": 0,
            "n_resolved": 0,
            "n_pending": 0,
            "n_with_odds": 0,
            "n_shortening": 0,
            "n_drifting": 0,
            "n_invalid": 0,
            "missing_fields": {},
            "pct_valid": 0.0,
        }

    n_total = len(picks_list)
    n_resolved = 0
    n_pending = 0
    n_with_odds = 0
    n_shortening = 0
    n_drifting = 0
    n_invalid = 0

    # Conta campos em falta por coluna
    expected_fields = [
        "data", "casa", "fora", "liga", "odds_over",
        "movimento", "xg_total", "btts_prob", "score_sistema",
        "result_over25", "clv",
    ]
    missing_counts = {f: 0 for f in expected_fields}

    for pick in picks_list:
        if not isinstance(pick, dict):
            n_invalid += 1
            continue

        # Campos em falta
        for field in expected_fields:
            val = pick.get(field)
            if val is None or val == "":
                missing_counts[field] += 1

        # Resolvido vs pendente
        result = pick.get("result_over25")
        if result in ("WIN", "LOSS"):
            n_resolved += 1
        elif result is None or result == "":
            n_pending += 1

        # Com odds
        odds = pick.get("odds_over")
        if odds is not None and odds != "":
            try:
                float(odds)
                n_with_odds += 1
            except (ValueError, TypeError):
                pass

        # Movimento
        mov = pick.get("movimento")
        if mov == "SHORTENING":
            n_shortening += 1
        elif mov == "DRIFTING":
            n_drifting += 1

    missing_fields = {k: v for k, v in missing_counts.items() if v > 0}
    pct_valid = round((n_total - n_invalid) / n_total * 100, 1) if n_total else 0.0

    return {
        "n_total": n_total,
        "n_resolved": n_resolved,
        "n_pending": n_pending,
        "n_with_odds": n_with_odds,
        "n_shortening": n_shortening,
        "n_drifting": n_drifting,
        "n_invalid": n_invalid,
        "missing_fields": missing_fields,
        "pct_valid": pct_valid,
    }
