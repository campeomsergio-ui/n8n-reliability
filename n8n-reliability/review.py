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


VOLATILE_KEY = ("$execution", "$now", "$today", "$runindex", "math.random", "$randomint", "uuid", "date.now")


def stable(value):
    v = str(value or "").lower()
    return bool(v.strip()) and not any(t in v for t in VOLATILE_KEY)


def has_idempotency(n):
    """An Idempotency-Key header that is actually sent, with a value that repeats on redelivery."""
    p = n.get("parameters") or {}
    if not n.get("type", "").endswith(".httpRequest") or not p.get("sendHeaders"):
        return False
    rows = (p.get("headerParameters") or {}).get("parameters") or []
    return any(str(h.get("name", "")).strip().lower() == "idempotency-key" and stable(h.get("value")) for h in rows if isinstance(h, dict))


def upsert_key(n):
    """Match value of an upsert, current (columns.matchingColumns) or legacy (valueToMatchOn) shape."""
    p = n.get("parameters") or {}
    if "valueToMatchOn" in p:
        return p["valueToMatchOn"]
    cols = p.get("columns") or {}
    match, vals = cols.get("matchingColumns") or [], cols.get("value") or {}
    return " ".join(str(vals.get(c, "")) for c in match) if match else None


def replay_safe_op(n):
    op = str((n.get("parameters") or {}).get("operation", "")).lower()
    if op == "upsert":
        key = upsert_key(n)
        return key is None or stable(key)  # no visible key: trust the node's own matching
    return op in REPLAY_SAFE_OPS


def is_dedupe(n):
    p = n.get("parameters") or {}
    return n.get("type", "").endswith("removeDuplicates") and p.get("operation") == "removeItemsSeenInPreviousExecutions" and stable(p.get("dedupeValue"))


def silent_fail(n):
    if "onError" in n:
        return n["onError"] == "continueRegularOutput"
    return bool(n.get("continueOnFail"))


def is_event_trigger(n):
    t = n.get("type", "")
    return (t.endswith(".webhook") or t.endswith("Trigger")) and not t.endswith(NON_EVENT_TRIGGERS)


def undeduped_path(target, starts, conns, by_name):
    """True if some trigger reaches target without passing a cross-execution dedupe node."""
    kids = {}
    for src, outs in conns.items():
        for branch in outs.get("main", []):
            for edge in branch or []:
                kids.setdefault(src, set()).add(edge["node"])
    seen, stack = set(starts), list(starts)
    while stack:
        for k in kids.get(stack.pop(), ()):
            if k == target:
                return True
            if k not in seen and not (k in by_name and is_dedupe(by_name[k])):
                seen.add(k); stack.append(k)
    return False


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
        op = str((n.get("parameters") or {}).get("operation", "")).lower()
        guarded = has_idempotency(n) or replay_safe_op(n)
        if n.get("retryOnFail") and not (guarded or op in REPLAY_SAFE_OPS):
            add("RETRY_WRITE", "high", n, f"Retry on fail is on (max tries {n.get('maxTries', 3)}) for a write with no idempotency key. A timeout after a successful write can create duplicates.",
                "Send an Idempotency-Key derived from a stable event ID, or switch to upsert. If neither is possible, turn retry off.")
        triggers = [a for a in ancestors(n["name"], conns) if a in by_name and is_event_trigger(by_name[a])]
        if triggers and not guarded and undeduped_path(n["name"], triggers, conns, by_name):
            add("REPLAY_WRITE", "high", n, "An event trigger reaches this write on a path with no cross-execution dedupe and no stable key. Providers redeliver events, and each delivery writes again.",
                "Add Remove Duplicates (across executions) keyed on the event ID before the write, or use upsert on the event ID.")
        if silent_fail(n):
            add("SILENT_FAIL", "medium", n, "Errors continue down the success path, so a failed write looks like a success.",
                "Use 'Continue (using error output)' and connect the error output to an alert, or stop the workflow.")
    return findings


USAGE = "usage: review.py WORKFLOW.json [...] [--format md|json|github]"


def main(argv):
    args, fmt = argv[1:], "md"
    if "--format" in args:
        i = args.index("--format")
        if i + 1 >= len(args) or args[i + 1] not in ("md", "json", "github"):
            print(USAGE, file=sys.stderr); return 2
        fmt = args[i + 1]; del args[i:i + 2]
    if not args or any(a.startswith("-") for a in args):
        print(USAGE, file=sys.stderr); return 2
    total, results = 0, []
    for path in args:
        try:
            with open(path, encoding="utf-8") as f:
                wf = json.load(f)
            if not isinstance(wf, dict) or not isinstance(wf.get("nodes", []), list):
                raise ValueError("not an n8n workflow export (expected an object with a nodes list)")
            fs = review(wf)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            print(f"{path}: cannot review: {e}", file=sys.stderr); return 2
        total += len(fs)
        results.append({"file": path, "workflow": wf.get("name"), "findings": fs})
    if fmt == "json":
        print(json.dumps(results, indent=2))
    for r in results if fmt != "json" else []:
        if fmt == "github":
            lvl = {"high": "error", "medium": "warning"}
            for x in r["findings"]:
                where = f" [{x['node']}]" if x["node"] else ""
                print(f"::{lvl.get(x['severity'], 'notice')} file={r['file']},title=n8n-reliability {x['rule']}::{x['finding']}{where} Fix: {x['fix']}")
            continue
        print(f"## {r['workflow'] or r['file']} ({r['file']}): {len(r['findings'])} finding(s)")
        for x in r["findings"]:
            where = f" [{x['node']} / {x['node_id']}]" if x["node"] else ""
            print(f"- {x['severity'].upper()} {x['rule']}{where}: {x['finding']}\n  Fix: {x['fix']}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
