# n8n-reliability

[![self-test](https://github.com/campeomsergio-ui/n8n-reliability/actions/workflows/self-test.yml/badge.svg)](https://github.com/campeomsergio-ui/n8n-reliability/actions/workflows/self-test.yml)
![python](https://img.shields.io/badge/python-3.8%2B-blue) ![deps](https://img.shields.io/badge/dependencies-none-brightgreen) ![license](https://img.shields.io/badge/license-MIT-lightgrey)

Static reliability review for exported **n8n** workflows. It reads the workflow JSON (never runs it) and flags the bugs that only show up in production: duplicate writes after a retry, events processed twice, failures that vanish silently, and webhooks that never answer.

## Run it

```bash
cd n8n-reliability
python3 review.py my-workflow.json                  # human-readable report
python3 review.py my-workflow.json --format json    # machine-readable
python3 review.py *.json --format github            # GitHub Actions annotations
```

Exit code is `1` when findings exist, so it drops straight into CI.

## Example

```text
## Order to CRM (fixtures/red/retry_write.json): 2 finding(s)
- HIGH RETRY_WRITE [Create deal / a2]: Retry on fail is on (max tries 3) for a write with no
  idempotency key. A timeout after a successful write can create duplicates.
  Fix: Send an Idempotency-Key derived from a stable event ID, or switch to upsert.
- HIGH REPLAY_WRITE [Create deal / a2]: An event trigger can reach this write on a path with no
  cross-execution dedupe and no stable key. If the provider redelivers the event, it can be written twice.
  Fix: Add Remove Duplicates (across executions) keyed on the event ID before the write, or use upsert.
```

## What it checks

| Rule | Bug it catches |
|---|---|
| `RETRY_WRITE` | Retry-on-fail on a non-idempotent write (duplicate records after a timeout) |
| `REPLAY_WRITE` | Event trigger can reach a write with no dedupe / stable key |
| `SILENT_FAIL` / `NO_ERROR_ROUTE` | Continue-on-fail or unwired error outputs that swallow failures |
| `WEBHOOK_NO_RESPONDER` | Webhook set to respond from a node that some path never reaches |
| Idempotency details | Header disabled, key built from non-stable text, Postgres upsert legacy vs current |

## How it is tested

Every rule has a **red/green fixture pair**: a minimal broken workflow that must trigger the rule and its fixed twin that must not. 15 pairs, 22 expectations, run on every push by CI. Fixtures are synthetic.

```bash
python3 tests/test_pairs.py && python3 tests/test_review_regressions.py
```

Also ships as a Claude skill (`SKILL.md`). Built by [Yuval Rochman](https://www.linkedin.com/in/yuval-rochman-206903452) · [GuraForge](https://guraforge.com).
