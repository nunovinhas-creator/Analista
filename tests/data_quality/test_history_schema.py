# test_history_schema.py — Testes pytest para o schema de football history
import pytest
from data.schema.history_schema import validate_history, history_quality_report


def _make_valid_record(**overrides):
    """Cria um registo de history válido com todos os campos."""
    base = {
        "date": "2026-05-22",
        "league": "Premier League",
        "home": "Arsenal",
        "away": "Chelsea",
        "hw": 52,
        "dr": 24,
        "aw": 24,
        "po": 71,
        "pb": 58,
        "xg_home": 1.8,
        "xg_away": 1.2,
        "conf": "ALTA",
        "pick_1x2": True,
        "hit_1x2": True,
        "pick_o25": True,
        "hit_o25": False,
        "pick_btts": False,
        "hit_btts": False,
    }
    base.update(overrides)
    return base


def _make_history_dict(records):
    return {"records": records}


def test_valid_history_passes():
    """3 registos válidos devem passar a validação."""
    records = [
        _make_valid_record(),
        _make_valid_record(home="Barcelona", away="Real Madrid", league="La Liga", conf="MÉDIA"),
        _make_valid_record(home="PSG", away="Lyon", league="Ligue 1", conf="BAIXA"),
    ]
    history = _make_history_dict(records)
    is_valid, errors, n = validate_history(history)
    assert n == 3, f"Esperado 3 registos, obtido {n}"
    assert is_valid is True, f"Esperado válido, mas erros: {errors}"
    assert errors == []


def test_invalid_probability_fails():
    """Registo com hw=150 (fora do range 0-100) deve falhar a validação."""
    records = [_make_valid_record(hw=150)]
    history = _make_history_dict(records)
    is_valid, errors, n = validate_history(history)
    assert is_valid is False, "Esperado inválido para hw=150"
    assert len(errors) > 0


def test_invalid_date_format_fails():
    """Registo com date='06/04/2026' (formato inválido) deve falhar."""
    records = [_make_valid_record(date="06/04/2026")]
    history = _make_history_dict(records)
    is_valid, errors, n = validate_history(history)
    assert is_valid is False, "Esperado inválido para formato de data errado"
    assert len(errors) > 0


def test_empty_records_handled():
    """validate_history({"records": []}) não deve lançar excepção."""
    result = validate_history({"records": []})
    assert isinstance(result, tuple), "Resultado deve ser um tuplo"
    assert len(result) == 3
    is_valid, errors, n = result
    assert n == 0
    assert isinstance(errors, list)
    assert isinstance(is_valid, bool)


def test_history_quality_report():
    """O relatório de qualidade deve conter as chaves e tipos correctos."""
    records = [
        _make_valid_record(),
        _make_valid_record(home="Porto", away="Benfica", league="Primeira Liga"),
    ]
    history = _make_history_dict(records)
    report = history_quality_report(history)

    expected_keys = {
        "n_records", "n_dates", "leagues_count",
        "avg_hw", "avg_dr", "avg_aw",
        "completeness", "date_range",
    }
    assert expected_keys.issubset(set(report.keys())), (
        f"Chaves em falta: {expected_keys - set(report.keys())}"
    )
    assert isinstance(report["n_records"], int)
    assert report["n_records"] == 2
    assert isinstance(report["leagues_count"], dict)
    assert isinstance(report["completeness"], dict)
    assert isinstance(report["date_range"], dict)
    assert "min_date" in report["date_range"]
    assert "max_date" in report["date_range"]

    # avg_hw deve ser um float ou None
    if report["avg_hw"] is not None:
        assert isinstance(report["avg_hw"], float)


def test_conf_values():
    """ALTA/MÉDIA/BAIXA devem ser aceites; 'MEDIA' (sem acento) deve falhar."""
    valid_records = [
        _make_valid_record(conf="ALTA"),
        _make_valid_record(conf="MÉDIA", home="B", away="C"),
        _make_valid_record(conf="BAIXA", home="D", away="E"),
    ]
    is_valid, errors, _ = validate_history(_make_history_dict(valid_records))
    assert is_valid is True, f"ALTA/MÉDIA/BAIXA devem ser válidos, erros: {errors}"

    invalid_records = [_make_valid_record(conf="MEDIA")]
    is_valid_bad, errors_bad, _ = validate_history(_make_history_dict(invalid_records))
    assert is_valid_bad is False, "'MEDIA' (sem acento) deve falhar"
    assert len(errors_bad) > 0
