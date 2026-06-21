from atsbench.scorers.rag_qa import facts_fraction, parse_judge_output


def test_facts_fraction():
    assert facts_fraction({"factfulness": {"facts_satisfied": [True, True, False]}}) == 2 / 3
    assert facts_fraction({"factfulness": {"facts_satisfied": []}}) == 0.0
    assert facts_fraction({}) == 0.0
    assert facts_fraction({"factfulness": {"facts_satisfied": [True, True]}}) == 1.0


def test_parse_judge_output():
    assert parse_judge_output('Here: {"factfulness": {"facts_satisfied": [true]}} done') == \
        {"factfulness": {"facts_satisfied": [True]}}
    assert parse_judge_output("no json at all") is None
