from inspect_ai.model import ModelUsage
from atsbench.report.aggregate import samples_from_log


class _S:
    def __init__(self, usage):
        self.model_usage = usage
        self.working_time = 1.0
        self.total_time = 1.0
        self.error = None


class _Log:
    def __init__(self, samples, model):
        self.samples = samples
        class E:  # eval header
            pass
        self.eval = E()
        self.eval.model = model


def test_samples_from_log_excludes_judge_tokens():
    usage = {
        "openrouter/z-ai/glm-5.2": ModelUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        "openrouter/anthropic/claude-3.7-sonnet": ModelUsage(input_tokens=900, output_tokens=400, total_tokens=1300),
    }
    log = _Log([_S(usage)], "openrouter/z-ai/glm-5.2")
    obs = samples_from_log(log, log.eval.model)
    assert len(obs) == 1
    assert obs[0].input_tokens == 100   # candidate only, judge's 900 excluded
    assert obs[0].output_tokens == 50
