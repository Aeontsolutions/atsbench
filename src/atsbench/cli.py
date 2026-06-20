from __future__ import annotations

import argparse
import json
import sys

from atsbench.config import load_models, load_workflows
from atsbench.report.build import build_scorecard_for_logs
from atsbench.report.render import render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atsbench")
    sub = parser.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("report", help="Aggregate eval logs into a gated scorecard.")
    rep.add_argument("--logs", required=True, help="Directory of Inspect .eval logs.")
    rep.add_argument("--workflow", required=True, help="Workflow name in workflows.yaml.")
    rep.add_argument("--models", default="models.yaml")
    rep.add_argument("--workflows", default="workflows.yaml")
    rep.add_argument("--json", dest="json_out", help="Optional path to write JSON.")

    args = parser.parse_args(argv)

    if args.command == "report":
        models = load_models(args.models)
        workflows = load_workflows(args.workflows)
        if args.workflow not in workflows:
            print(f"Unknown workflow: {args.workflow}", file=sys.stderr)
            return 2
        wf = workflows[args.workflow]
        card = build_scorecard_for_logs(args.logs, wf, models)
        print(render_markdown(wf.name, card))
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(render_json(wf.name, card), f, indent=2)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
