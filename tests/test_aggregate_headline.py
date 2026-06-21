from dataclasses import dataclass

from atsbench.report.aggregate import accuracy_from_log


@dataclass
class _M:
    value: float


@dataclass
class _S:
    metrics: dict


@dataclass
class _R:
    scores: list


@dataclass
class _Log:
    results: object


def test_prefers_accuracy_then_mean():
    log_acc = _Log(_R([_S({"accuracy": _M(0.9), "mean": _M(0.5)})]))
    assert accuracy_from_log(log_acc) == 0.9

    log_mean = _Log(_R([_S({"mean": _M(0.77), "stderr": _M(0.1)})]))
    assert accuracy_from_log(log_mean) == 0.77


def test_falls_back_to_first_metric():
    log_other = _Log(_R([_S({"f1": _M(0.42)})]))
    assert accuracy_from_log(log_other) == 0.42


def test_no_results_is_zero():
    assert accuracy_from_log(_Log(None)) == 0.0
