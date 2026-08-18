"""Command-line entry point (PRD-08):

    python -m attack_simulator.cli obfuscated_sqli --base-url https://xxx.execute-api.us-east-1.amazonaws.com/Prod
    python -m attack_simulator.cli all --base-url http://localhost:3000

Needs no CockroachDB/AWS credentials -- this only sends HTTP requests to a
deployed (or local) demo-target-app instance. The patrol agent picks up
the resulting `request_logs` rows on its next scheduled round; there's no
direct integration between this tool and PatrolAgentLambda.
"""
import argparse
import sys
import time

from .http_client import HttpClient
from .scenarios import SCENARIOS


def build_parser():
    parser = argparse.ArgumentParser(description="CR-Sentinel attack simulator (PRD-08)")
    parser.add_argument(
        "scenario", choices=sorted(SCENARIOS) + ["all"], help="which scenario to run, or 'all' to run every scenario in sequence"
    )
    parser.add_argument("--base-url", required=True, help="base URL of the demo-target-app deployment, e.g. an API Gateway stage URL")
    return parser


def main(argv=None, client_factory=HttpClient, sleep_fn=time.sleep):
    """`sleep_fn` is forwarded into each scenario's `run()` rather than
    relying on tests monkeypatching `time.sleep` globally -- scenario
    modules default their own `sleep_fn` parameter to `time.sleep` at
    import time, so a later `time.sleep` monkeypatch wouldn't reach an
    already-bound default. Explicit injection avoids that trap."""
    args = build_parser().parse_args(argv)
    client = client_factory(args.base_url)

    names = sorted(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for name in names:
        result = SCENARIOS[name].run(client, sleep_fn=sleep_fn)
        print(f"\n[{result.name}] done -- {result.requests_sent} requests sent.")
        print(f"  Expected verdict: risk_level={result.expected_risk_level} attack_type={result.expected_attack_type}")
        print(f"  Narrative: {result.narrative}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
