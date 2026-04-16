import pytest

from report_building_agent.tools import _safe_eval_arithmetic


def test_safe_eval_ok():
    assert _safe_eval_arithmetic("2 + 2") == 4.0
    assert _safe_eval_arithmetic("10 / 4") == 2.5
    assert _safe_eval_arithmetic("(5 + 3) * 2") == 16.0


def test_safe_eval_rejects_calls():
    with pytest.raises(ValueError):
        _safe_eval_arithmetic("__import__('os').system('echo pwned')")


def test_safe_eval_rejects_power():
    with pytest.raises(ValueError):
        _safe_eval_arithmetic("2 ** 10")
