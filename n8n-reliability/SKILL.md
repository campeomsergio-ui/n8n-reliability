---
name: n8n-reliability
description: Reviews an exported n8n workflow JSON for duplicate writes on retry or event redelivery, failures that pass silently down the success path, and missing error alerts. Use when the user shares an n8n workflow export, or asks whether a workflow is safe to hand over or will double-write.
---

# n8n Workflow Reliability Review

Reads exported workflow files only. It never imports, activates or runs a workflow, and makes no network calls.

## Steps
1. Ask the user for the workflow export (n8n: Workflow menu > Download). Ask them to remove credentials and personal data first. Exports normally hold credential references, not secrets.
2. Run `python3 review.py path/to/workflow.json` (Python 3, standard library only). Exit code 0 means no findings and 1 means findings. 2 means a usage error.
3. For every finding, report the node name and node ID, what the setting is now, why it matters, and the fix.
4. Then list the **unknowns** that a static file cannot answer. Examples are whether the target API honours Idempotency-Key, whether the provider redelivers events, and whether the error workflow actually notifies someone.
5. End with a replay test table. Give one row per high finding: the action (send the same event twice, or force a timeout after the write), the expected result (one record) and where to check.

## Checks
- RETRY_WRITE (high): retry on fail is on for a write (POST/PUT/PATCH/DELETE, or a create/insert/send-style operation) with no sent Idempotency-Key header. Upsert, update and delete are treated as retry-safe.
- REPLAY_WRITE (high): an event trigger (webhook or app trigger) reaches a write by some path that skips a Remove Duplicates node set to "previous executions" with a dedupe value, and the write has no stable Idempotency-Key and is not an upsert on a stable key. Keys built from `$execution`, `$now`, random values or UUIDs count as unstable.
- SILENT_FAIL (medium): a write continues on error through the regular output (`onError` wins over the older `continueOnFail`).
- NO_ERROR_ROUTE (medium): the workflow writes but has no error workflow.

`--format json` prints machine-readable findings; `--format github` prints GitHub Actions annotations.

## Limits
Static heuristics only. A clean report means none of these four patterns were found. It does not mean the workflow is reliable. Write detection relies on the HTTP method or the node's `operation` value, so custom or community nodes can be missed. If you want a person to fix what it finds: https://guraforge.com
