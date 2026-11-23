---
name: n8n-reliability
description: Flags settings in an exported n8n workflow that are linked to duplicate writes, dropped failures and unanswered webhooks (retry without an idempotency key, event redelivery without cross-run dedupe, errors continuing as success, unwired error outputs, missing Respond to Webhook, no error handler). Use when the user shares an n8n workflow export, or asks whether a workflow can double-write or fail silently.
---

# n8n Workflow Reliability Review

`review.py` reads local workflow JSON. It never imports, activates or runs a workflow, and makes no network calls.

## Steps
1. Ask the user for the workflow export (n8n: Workflow menu > Download). Exports hold credential names and IDs and can contain auth headers or personal data, so ask for a redacted copy.
2. Run `python3 review.py path/to/workflow.json` (Python 3, standard library only). Exit 0 means no flagged findings, 1 means findings, 2 means a usage error or a file it could not read as a workflow. Add `--format json` or `--format github` for CI.
3. For every finding, report the node (workflow-level findings have none), the current setting, why it matters and the suggested fix.
4. List the **unknowns** a static file cannot answer: whether the target API honours Idempotency-Key, whether the provider redelivers events, whether the error workflow really notifies someone, writes built from expressions, SQL inside Execute Query, and which branches run in practice.
5. End with a replay test table, one row per high finding: the action (send the same synthetic event twice, or force a timeout after the write), the expected result (one record, or one downstream side effect) and where to check.

## Checks
- RETRY_WRITE (high): retry on fail is on for a write (POST/PUT/PATCH/DELETE, or a create/insert/send-style operation) with no Idempotency-Key header that is actually sent. Upsert, update and delete count as retry-safe.
- REPLAY_WRITE (high): an event trigger can reach a write on a path that skips a Remove Duplicates node set to previous executions with a dedupe value, and the write has no stable Idempotency-Key and is not an upsert on a stable key. Keys built from `$execution`, `$now`, random values or UUIDs count as unstable.
- NO_WEBHOOK_RESPONSE (high/medium): the webhook answers via a Respond to Webhook node, but there is none, or some route ends before reaching it.
- UNWIRED_ERROR_OUTPUT (medium): a write sends errors to its error output and nothing is connected to it.
- SILENT_FAIL (medium): a write continues on error through the regular output (`onError` wins over the older `continueOnFail`).
- NO_ERROR_ROUTE (medium): the workflow writes, and no workflow-level error handler was found in the export.

## Limits
Static heuristics only. A clean report means none of these patterns were found, not that the workflow is reliable. Write detection relies on the HTTP method or the node's `operation` value, so custom or community nodes can be missed. Confirm API behaviour, dedupe and alert delivery with a runtime test. If you want a person to fix what it finds: https://guraforge.com
