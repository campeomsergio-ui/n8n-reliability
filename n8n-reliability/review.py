#!/usr/bin/env python3
"""Static reliability review of an exported n8n workflow JSON. Reads files only; never runs workflows."""
import json, sys

WRITE_OPS = {"create", "insert", "append", "send", "post", "update", "delete", "upsert", "add"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REPLAY_SAFE_OPS = {"upsert", "update", "delete"}
NON_EVENT_TRIGGERS = ("scheduleTrigger", "manualTrigger", "cron", "errorTrigger", "executeWorkflowTrigger")


def is_write(n):
    p = n.get("parameters") or {}
    if n.get("type", "").endswith(".httpRequest"):
        return str(p.get("method", "GET")).upper() in WRITE_METHODS
    return str(p.get("operation", "")).lower() in WRITE_OPS


def has_idempotency(n):
    return "idempotency" in json.dumps(n.get("parameters") or {}).lower()


def is_event_trigger(n):
    t = n.get("type", "")
    return (t.endswith(".webhook") or t.endswith("Trigger")) and not t.endswith(NON_EVENT_TRIGGERS)


def ancestors(name, conns):
    parents = {}
    for src, outs in conns.items():
        for branch in outs.get("main", []):
            for edge in branch or []:
                parents.setdefault(edge["node"], set()).add(src)
    seen, stack = set(), [name]
    while stack:
        for p in parents.get(stack.pop(), ()):
            if p not in seen:
                seen.add(p); stack.append(p)
    return seen


def review(wf):
    nodes = wf.get("nodes", [])
    by_name = {n["name"]: n for n in nodes}
    conns = wf.get("connections", {})
    writes = [n for n in nodes if is_write(n)]
    findings = []

    def add(rule, sev, n, msg, fix):
        findings.append({"rule": rule, "severity": sev, "node_id": n.get("id") if n else None,
                         "node": n.get("name") if n else None, "finding": msg, "fix": fix})

    has_error_route = bool((wf.get("settings") or {}).get("errorWorkflow")) or any(
        n.get("type", "").endswith("errorTrigger") for n in nodes)
    if writes and not has_error_route:
        add("NO_ERROR_ROUTE", "medium", None, "No error workflow is set, so a failed run alerts nobody.",
            "Set Settings > Error workflow to a workflow that starts with an Error Trigger and notifies a person.")

    for n in writes:
        p = n.get("parameters") or {}
        op = str(p.get("operation", "")).lower()
        guarded = has_idempotency(n)
        if n.get("retryOnFail") and not guarded:
            add("RETRY_WRITE", "high", n, f"Retry on fail is on (max tries {n.get('maxTries', 3)}) for a write with no idempotency key. A timeout after a successful write can create duplicates.",
                "Send an Idempotency-Key derived from a stable event ID, or switch to upsert. If neither is possible, turn retry off.")
        ups = {by_name[a].get("type", "") for a in ancestors(n["name"], conns) if a in by_name}
        event_fed = any(is_event_trigger(by_name[a]) for a in ancestors(n["name"], conns) if a in by_name)
        deduped = any(t.endswith("removeDuplicates") for t in ups)
        if event_fed and not (deduped or guarded or op in REPLAY_SAFE_OPS):
            add("REPLAY_WRITE", "high", n, "An event trigger feeds this write with no dedupe step. Providers redeliver events, and each delivery writes again.",
                "Add Remove Duplicates (across executions) keyed on the event ID before the write, or use upsert on the event ID.")
        if n.get("continueOnFail") or n.get("onError") == "continueRegularOutput":
            add("SILENT_FAIL", "medium", n, "Errors continue down the success path, so a failed write looks like a success.",
                "Use 'Continue (using error output)' and connect the error output to an alert, or stop the workflow.")
    return findings


def main(argv):
    if len(argv) < 2:
        print("usage: review.py WORKFLOW.json [...]", file=sys.stderr); return 2
    total = 0
    for path in argv[1:]:
        with open(path) as f:
            wf = json.load(f)
        fs = review(wf)
        total += len(fs)
        print(f"## {wf.get('name', path)} ({path}): {len(fs)} finding(s)")
        for x in fs:
            where = f" [{x['node']} / {x['node_id']}]" if x["node"] else ""
            print(f"- {x['severity'].upper()} {x['rule']}{where}: {x['finding']}\n  Fix: {x['fix']}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
