# attack-simulator

Command-line attack scripts (PRD-08) for driving traffic at a deployed
`demo-target-app` (PRD-02) instance -- both for development self-testing
and as the core material for the submission demo video (PRD-10). Directly
demonstrates the "traditional WAF misses this, semantic AI catches it"
scenarios `rawmaterial.txt` calls out.

This is a demo tool, not a test framework or a new deployed service: it
sends plain HTTP requests over the network and prints its progress. It
has no CockroachDB/AWS credentials and no direct integration with the
patrol agent -- the traffic it generates lands in `request_logs` the same
way any real request would, and `PatrolAgentLambda` picks it up on its
next scheduled round (PRD-04's `PatrolIntervalMinutes`).

## Scenarios

Four of PRD-08's eight scenarios, chosen for being both visually clear in
a short demo video and hard for a traditional signature/regex WAF:

| Scenario | What it sends | Why a keyword/regex WAF misses it |
|---|---|---|
| `obfuscated_sqli` | The same `UNION SELECT` intent, 4 different ways (plain, case-mixed, URL-encoded, `/**/`-split) to `GET /profile?id=` | Needs one rule per variant; the patrol agent should recognize all 4 as one attack via semantic embedding recall against `attack_signatures`, not string matching |
| `slow_bruteforce` | 6 wrong passwords for one username against `POST /login`, spaced out | Too slow to trip a fixed request-count threshold in one patrol window; the pattern across `agent_episodes` history is what should read as brute force |
| `idor_enumeration` | 10 sequential `id` values against `GET /profile` | Every request is syntactically normal -- no payload to match on, the attack only exists in the *sequence* |
| `chained_intrusion` | probe `/admin` -> weak-credential login -> IDOR reads -> re-probe `/admin`, one IP | Each step alone looks like ordinary traffic; only the full chain (and Claude weighing `agent_episodes` across it) should read as an intrusion |

Each scenario's expected verdict (`risk_level`/`attack_type`) and a short
narrative for the demo script are printed after it runs -- see
`attack_simulator/scenarios/*.py` for the reasoning behind each pick.

## Usage

```bash
pip install -r requirements.txt   # no third-party deps today, kept for convention
python -m attack_simulator.cli obfuscated_sqli --base-url https://xxx.execute-api.us-east-1.amazonaws.com/Prod
python -m attack_simulator.cli all --base-url http://localhost:3000
```

`--base-url` is whatever `demo-target-app/template.yaml`'s `ApiUrl` output
resolves to once deployed (or a local API Gateway/SAM-local endpoint).
After running a scenario, wait for the next patrol round
(`PATROL_WINDOW_MINUTES`) and check `alert_log`/`ip_blacklist`/Dashboard
(PRD-07) for the resulting verdict.

## Layout

```
attack_simulator/
  http_client.py   HttpClient -- urllib.request wrapper, injectable transport for tests
  scenarios/
    base.py            ScenarioResult dataclass
    obfuscated_sqli.py
    slow_bruteforce.py
    idor_enumeration.py
    chained_intrusion.py
  cli.py             python -m attack_simulator.cli <scenario> --base-url ...
tests/               Unit tests against a fake HTTP client -- no live network needed
```

## Local development

```bash
python -m pytest -q
```

Every scenario's `run()` takes an injectable `sleep_fn` (defaulting to
`time.sleep`), and `cli.main()` forwards a `sleep_fn` override down to
whichever scenario it runs -- tests pass a no-op so the suite runs
instantly instead of waiting through each scenario's real delays.
