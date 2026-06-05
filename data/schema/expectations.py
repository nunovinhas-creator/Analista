# expectations.py — Great Expectations-inspired data expectations (sem pacote GE)
import pandas as pd
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Expectation:
    """Resultado de uma expectativa de dados."""
    name: str
    passed: bool
    value: Any
    expected: Any
    message: str


class DataExpectations:
    """Conjunto de expectativas de dados ao estilo Great Expectations.

    Uso:
        de = DataExpectations()
        de.register(de.expect_column_not_null, df, "casa")
        results = de.run_all(df)
        print(de.summary())
    """

    def __init__(self):
        # Lista de (func, args, kwargs) registados para run_all
        self._registered: List[tuple] = []

    # ------------------------------------------------------------------
    # Métodos de expectativa individuais
    # ------------------------------------------------------------------

    def expect_column_not_null(self, df: pd.DataFrame, col: str) -> Expectation:
        """Verifica que a coluna não tem valores nulos."""
        if col not in df.columns:
            return Expectation(
                name=f"expect_column_not_null[{col}]",
                passed=False,
                value=None,
                expected="coluna existe e sem nulos",
                message=f"Coluna '{col}' não existe no DataFrame",
            )
        n_null = int(df[col].isna().sum())
        passed = n_null == 0
        return Expectation(
            name=f"expect_column_not_null[{col}]",
            passed=passed,
            value=n_null,
            expected=0,
            message=(
                f"OK — '{col}' sem nulos"
                if passed
                else f"FALHOU — '{col}' tem {n_null} valor(es) nulo(s)"
            ),
        )

    def expect_column_values_in_set(
        self, df: pd.DataFrame, col: str, values: list
    ) -> Expectation:
        """Verifica que todos os valores não-nulos da coluna pertencem ao conjunto."""
        if col not in df.columns:
            return Expectation(
                name=f"expect_column_values_in_set[{col}]",
                passed=False,
                value=None,
                expected=values,
                message=f"Coluna '{col}' não existe no DataFrame",
            )
        valid_set = set(v for v in values if v is not None)
        non_null = df[col].dropna()
        invalid = non_null[~non_null.isin(valid_set)]
        n_invalid = len(invalid)
        passed = n_invalid == 0
        return Expectation(
            name=f"expect_column_values_in_set[{col}]",
            passed=passed,
            value=int(n_invalid),
            expected=values,
            message=(
                f"OK — '{col}' todos os valores no conjunto"
                if passed
                else f"FALHOU — '{col}' tem {n_invalid} valor(es) fora do conjunto: {invalid.unique().tolist()}"
            ),
        )

    def expect_column_values_between(
        self,
        df: pd.DataFrame,
        col: str,
        min_val: float,
        max_val: float,
        coerce: bool = True,
    ) -> Expectation:
        """Verifica que os valores numéricos estão no intervalo [min_val, max_val]."""
        if col not in df.columns:
            return Expectation(
                name=f"expect_column_values_between[{col}]",
                passed=False,
                value=None,
                expected=f"[{min_val}, {max_val}]",
                message=f"Coluna '{col}' não existe no DataFrame",
            )
        series = pd.to_numeric(df[col], errors="coerce") if coerce else df[col]
        non_null = series.dropna()
        out_of_range = non_null[(non_null < min_val) | (non_null > max_val)]
        n_invalid = len(out_of_range)
        passed = n_invalid == 0
        return Expectation(
            name=f"expect_column_values_between[{col}]",
            passed=passed,
            value=int(n_invalid),
            expected=f"[{min_val}, {max_val}]",
            message=(
                f"OK — '{col}' todos os valores entre {min_val} e {max_val}"
                if passed
                else f"FALHOU — '{col}' tem {n_invalid} valor(es) fora de [{min_val}, {max_val}]"
            ),
        )

    def expect_column_unique_count_between(
        self,
        df: pd.DataFrame,
        col: str,
        min_n: int,
        max_n: Optional[int] = None,
    ) -> Expectation:
        """Verifica que o número de valores únicos está no intervalo esperado."""
        if col not in df.columns:
            return Expectation(
                name=f"expect_column_unique_count_between[{col}]",
                passed=False,
                value=None,
                expected=f">= {min_n}" if max_n is None else f"[{min_n}, {max_n}]",
                message=f"Coluna '{col}' não existe no DataFrame",
            )
        n_unique = int(df[col].nunique(dropna=True))
        if max_n is None:
            passed = n_unique >= min_n
            expected_str = f">= {min_n}"
        else:
            passed = min_n <= n_unique <= max_n
            expected_str = f"[{min_n}, {max_n}]"
        return Expectation(
            name=f"expect_column_unique_count_between[{col}]",
            passed=passed,
            value=n_unique,
            expected=expected_str,
            message=(
                f"OK — '{col}' tem {n_unique} valores únicos"
                if passed
                else f"FALHOU — '{col}' tem {n_unique} valores únicos, esperado {expected_str}"
            ),
        )

    def expect_row_count_between(
        self,
        df: pd.DataFrame,
        min_n: int,
        max_n: Optional[int] = None,
    ) -> Expectation:
        """Verifica que o número de linhas está no intervalo esperado."""
        n_rows = len(df)
        if max_n is None:
            passed = n_rows >= min_n
            expected_str = f">= {min_n}"
        else:
            passed = min_n <= n_rows <= max_n
            expected_str = f"[{min_n}, {max_n}]"
        return Expectation(
            name="expect_row_count_between",
            passed=passed,
            value=n_rows,
            expected=expected_str,
            message=(
                f"OK — DataFrame tem {n_rows} linhas"
                if passed
                else f"FALHOU — DataFrame tem {n_rows} linhas, esperado {expected_str}"
            ),
        )

    def expect_column_mean_between(
        self,
        df: pd.DataFrame,
        col: str,
        min_val: float,
        max_val: float,
    ) -> Expectation:
        """Verifica que a média da coluna está no intervalo [min_val, max_val]."""
        if col not in df.columns:
            return Expectation(
                name=f"expect_column_mean_between[{col}]",
                passed=False,
                value=None,
                expected=f"[{min_val}, {max_val}]",
                message=f"Coluna '{col}' não existe no DataFrame",
            )
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) == 0:
            return Expectation(
                name=f"expect_column_mean_between[{col}]",
                passed=False,
                value=None,
                expected=f"[{min_val}, {max_val}]",
                message=f"FALHOU — '{col}' não tem valores numéricos para calcular média",
            )
        mean_val = float(series.mean())
        passed = min_val <= mean_val <= max_val
        return Expectation(
            name=f"expect_column_mean_between[{col}]",
            passed=passed,
            value=round(mean_val, 4),
            expected=f"[{min_val}, {max_val}]",
            message=(
                f"OK — '{col}' média {mean_val:.4f} dentro de [{min_val}, {max_val}]"
                if passed
                else f"FALHOU — '{col}' média {mean_val:.4f} fora de [{min_val}, {max_val}]"
            ),
        )

    # ------------------------------------------------------------------
    # Registo e execução em lote
    # ------------------------------------------------------------------

    def register(self, func, *args, **kwargs):
        """Regista uma expectativa para execução em run_all."""
        self._registered.append((func, args, kwargs))

    def run_all(self, df: pd.DataFrame) -> List[Expectation]:
        """Executa todas as expectativas registadas e retorna lista de resultados."""
        results = []
        for func, args, kwargs in self._registered:
            try:
                result = func(df, *args, **kwargs)
                results.append(result)
            except Exception as e:
                results.append(
                    Expectation(
                        name=getattr(func, "__name__", "unknown"),
                        passed=False,
                        value=None,
                        expected=None,
                        message=f"Excepção durante execução: {e}",
                    )
                )
        self._last_results = results
        return results

    def summary(self) -> dict:
        """Retorna sumário dos resultados das expectativas registadas."""
        results = getattr(self, "_last_results", [])
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        pass_rate = round(passed / total * 100, 1) if total > 0 else 0.0
        return {
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": pass_rate,
        }


# ------------------------------------------------------------------
# Funções de conveniência para picks e history
# ------------------------------------------------------------------

def run_picks_expectations(picks_list) -> dict:
    """Executa expectativas padrão para dados de picks Over 2.5.

    Retorna dict com sumário e detalhes dos resultados.
    """
    if not picks_list:
        return {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0, "details": []}

    try:
        df = pd.DataFrame(picks_list)
    except Exception as e:
        return {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0,
                "details": [{"name": "build_dataframe", "passed": False, "message": str(e)}]}

    de = DataExpectations()

    # Expectativas de linha
    de.register(de.expect_row_count_between, 1)

    # Campos obrigatórios
    for col in ("data", "casa", "fora"):
        de.register(de.expect_column_not_null, col)

    # Odds num intervalo razoável
    de.register(de.expect_column_values_between, "odds_over", 1.01, 50.0)

    # Movimento — só valores válidos (não nulos)
    de.register(de.expect_column_values_in_set, "movimento", ["SHORTENING", "DRIFTING"])

    # Probabilidades
    de.register(de.expect_column_values_between, "btts_prob", 0.0, 1.0)
    de.register(de.expect_column_values_between, "xg_total", 0.0, 20.0)
    de.register(de.expect_column_values_between, "score_sistema", 0.0, 100.0)

    # Ligas — pelo menos 1 liga distinta
    de.register(de.expect_column_unique_count_between, "liga", 1)

    results = de.run_all(df)
    summ = de.summary()
    summ["details"] = [
        {"name": r.name, "passed": r.passed, "value": r.value, "message": r.message}
        for r in results
    ]
    return summ


def run_history_expectations(history_dict) -> dict:
    """Executa expectativas padrão para dados do football history.

    Retorna dict com sumário e detalhes dos resultados.
    """
    if not isinstance(history_dict, dict):
        return {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0,
                "details": [{"name": "input_type", "passed": False,
                              "message": "history_dict não é um dicionário"}]}

    records = history_dict.get("records", [])
    if not records:
        return {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0, "details": []}

    try:
        df = pd.DataFrame(records)
    except Exception as e:
        return {"passed": 0, "failed": 1, "total": 1, "pass_rate": 0.0,
                "details": [{"name": "build_dataframe", "passed": False, "message": str(e)}]}

    de = DataExpectations()

    # Expectativas de linha
    de.register(de.expect_row_count_between, 1)

    # Campos obrigatórios
    for col in ("date", "home", "away"):
        de.register(de.expect_column_not_null, col)

    # Probabilidades em escala 0-100
    for col in ("hw", "dr", "aw", "po", "pb"):
        de.register(de.expect_column_values_between, col, 0.0, 100.0)

    # Confiança
    de.register(
        de.expect_column_values_in_set, "conf", ["ALTA", "MÉDIA", "BAIXA"]
    )

    # Média de hw razoável (não todos 0 ou 100)
    de.register(de.expect_column_mean_between, "hw", 1.0, 99.0)

    # Ligas distintas
    de.register(de.expect_column_unique_count_between, "league", 1)

    results = de.run_all(df)
    summ = de.summary()
    summ["details"] = [
        {"name": r.name, "passed": r.passed, "value": r.value, "message": r.message}
        for r in results
    ]
    return summ
