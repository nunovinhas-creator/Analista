# test_picks_schema.py — Testes pytest para o schema de picks Over 2.5
import pytest
from data.schema.picks_schema import validate_picks, picks_quality_report


def _make_valid_pick(**overrides):
    """Cria um pick válido com todos os campos obrigatórios."""
    base = {
        "data": "2026-05-01T18:00:00",
        "casa": "Arsenal",
        "fora": "Chelsea",
        "liga": "Premier League",
        "odds_over": "1.85",
        "movimento": "SHORTENING",
        "xg_total": "2.8",
        "btts_prob": "0.62",
        "score_sistema": "78",
        "result_over25": "WIN",
        "clv": "-0.05",
    }
    base.update(overrides)
    return base


def test_valid_picks_passes_schema():
    """5 picks válidos devem passar a validação sem erros."""
    picks = [
        _make_valid_pick(casa="Arsenal", fora="Chelsea", result_over25="WIN"),
        _make_valid_pick(casa="Barcelona", fora="Real Madrid", movimento="DRIFTING", result_over25="LOSS"),
        _make_valid_pick(casa="PSG", fora="Lyon", odds_over="2.10", result_over25=None),
        _make_valid_pick(casa="Benfica", fora="Porto", score_sistema="55", result_over25=""),
        _make_valid_pick(casa="Juventus", fora="Milan", xg_total="3.1", clv=None),
    ]
    is_valid, errors, n = validate_picks(picks)
    assert n == 5, f"Esperado 5 registos, obtido {n}"
    assert is_valid is True, f"Esperado válido, mas erros: {errors}"
    assert errors == []


def test_invalid_odds_fails():
    """Pick com odds_over='-1.0' (fora do range 1.01-50.0) deve falhar a validação."""
    picks = [_make_valid_pick(odds_over="-1.0")]
    is_valid, errors, n = validate_picks(picks)
    assert is_valid is False, "Esperado inválido para odds negativas"
    assert len(errors) > 0, "Esperado pelo menos um erro"


def test_missing_required_field_fails():
    """Pick sem campo 'casa' (not null) deve falhar a validação."""
    pick = {
        "data": "2026-05-01T18:00:00",
        # "casa" ausente
        "fora": "Chelsea",
        "liga": "Premier League",
        "odds_over": "1.85",
        "movimento": "SHORTENING",
        "xg_total": "2.8",
        "btts_prob": "0.62",
        "score_sistema": "78",
        "result_over25": "WIN",
        "clv": "-0.05",
    }
    is_valid, errors, n = validate_picks([pick])
    assert is_valid is False, "Esperado inválido para campo obrigatório em falta"
    assert len(errors) > 0


def test_empty_list_handled():
    """validate_picks([]) não deve lançar excepção e retorna tuplo válido."""
    result = validate_picks([])
    assert isinstance(result, tuple), "Resultado deve ser um tuplo"
    assert len(result) == 3, "Tuplo deve ter 3 elementos (is_valid, errors, n)"
    is_valid, errors, n = result
    assert n == 0
    assert isinstance(errors, list)
    assert isinstance(is_valid, bool)


def test_picks_quality_report_structure():
    """O relatório de qualidade deve conter todas as chaves esperadas."""
    picks = [_make_valid_pick(), _make_valid_pick(casa="Porto", fora="Braga")]
    report = picks_quality_report(picks)
    expected_keys = {
        "n_total", "n_resolved", "n_pending", "n_with_odds",
        "n_shortening", "n_drifting", "n_invalid", "missing_fields", "pct_valid",
    }
    assert expected_keys.issubset(set(report.keys())), (
        f"Chaves em falta: {expected_keys - set(report.keys())}"
    )
    assert isinstance(report["n_total"], int)
    assert isinstance(report["missing_fields"], dict)
    assert isinstance(report["pct_valid"], float)


def test_result_values_valid():
    """WIN/LOSS/None devem ser aceites; 'UNKNOWN' deve falhar."""
    valid_picks = [
        _make_valid_pick(result_over25="WIN"),
        _make_valid_pick(result_over25="LOSS", casa="B", fora="C"),
        _make_valid_pick(result_over25=None, casa="D", fora="E"),
        _make_valid_pick(result_over25="", casa="F", fora="G"),
    ]
    is_valid, errors, n = validate_picks(valid_picks)
    assert is_valid is True, f"WIN/LOSS/None/'''' devem ser válidos, erros: {errors}"

    invalid_pick = [_make_valid_pick(result_over25="UNKNOWN")]
    is_valid_bad, errors_bad, _ = validate_picks(invalid_pick)
    assert is_valid_bad is False, "UNKNOWN deve falhar a validação"
    assert len(errors_bad) > 0
