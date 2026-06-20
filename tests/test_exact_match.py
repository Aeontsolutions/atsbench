from atsbench.scorers.exact_match import exact_match_score, normalize


def test_normalize_strips_and_lowercases():
    assert normalize("  Hello World  ") == "hello world"


def test_exact_match_score():
    assert exact_match_score("Yes", "yes") is True
    assert exact_match_score("no", "yes") is False
