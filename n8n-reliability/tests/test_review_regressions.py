"""Expected findings for synthetic workflows shaped like n8n exports."""

import json
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL))
from review import review

RETRY_AND_REPLAY = {"RETRY_WRITE", "REPLAY_WRITE"}
EXPECTATIONS = {
    "http_disabled_idempotency_header": (RETRY_AND_REPLAY, set()),
    "http_idempotency_body_text": (RETRY_AND_REPLAY, set()),
    "dedupe_within_execution": ({"REPLAY_WRITE"}, set()),
    "dedupe_clear_history": ({"REPLAY_WRITE"}, set()),
    "dedupe_bypass_branch": ({"REPLAY_WRITE"}, set()),
    "postgres_upsert_current": ({"REPLAY_WRITE"}, set()),
    "postgres_upsert_legacy": ({"REPLAY_WRITE"}, set()),
    "on_error_overrides_legacy": ({"SILENT_FAIL"}, set()),
    "unwired_error_output": ({"UNWIRED_ERROR_OUTPUT"}, set()),
    "webhook_response_bypassed": ({"NO_WEBHOOK_RESPONSE"}, set()),
    "webhook_no_responder": ({"NO_WEBHOOK_RESPONSE"}, set()),
}


def main():
    failures = 0
    for name, (red, green) in EXPECTATIONS.items():
        for side, expected in (("red", red), ("green", green)):
            fixture = SKILL / "fixtures" / side / f"{name}.json"
            findings = review(json.loads(fixture.read_text()))
            actual = {finding["rule"] for finding in findings}
            matches = actual == expected
            failures += not matches
            result = "ok" if matches else "FAIL"
            print(f"{result:4} {side}/{name} expected={sorted(expected)} actual={sorted(actual)}")
    print(f"{2 * len(EXPECTATIONS) - failures}/{2 * len(EXPECTATIONS)} expectations met")
    return int(failures > 0)


if __name__ == "__main__":
    sys.exit(main())
