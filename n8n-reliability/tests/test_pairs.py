import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from review import review
F = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
EXPECT = {"retry_write": {"RETRY_WRITE", "REPLAY_WRITE"}, "no_error_route": {"NO_ERROR_ROUTE"},
          "silent_fail": {"SILENT_FAIL"}, "webhook_nodedupe": {"REPLAY_WRITE"}}
bad = 0
for name, rules in EXPECT.items():
    red = {x["rule"] for x in review(json.loads((F / "red" / f"{name}.json").read_text()))}
    green = review(json.loads((F / "green" / f"{name}.json").read_text()))
    ok = red == rules and not green
    bad += not ok
    print(("ok  " if ok else "FAIL"), name, sorted(red), [x["rule"] for x in green])
sys.exit(bad)
