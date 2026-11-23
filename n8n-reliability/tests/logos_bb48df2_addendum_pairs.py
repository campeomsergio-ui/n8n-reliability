"""Synthetic workflow-export and annotation pairs for cc7b0fa."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL))
from review import review


class ReviewPairs(unittest.TestCase):
    def test_disabled_writes(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                node = {"name": "Write", "type": "n8n-nodes-base.httpRequest",
                        "parameters": {"method": "POST"}, "retryOnFail": True,
                        "disabled": disabled}
                rules = {f["rule"] for f in review({"nodes": [node]})}
                self.assertEqual(rules, set() if disabled else {"NO_ERROR_ROUTE", "RETRY_WRITE"})

    def test_retry_upsert_key(self):
        for key, expected in (("={{ $json.eventId }}", False), ("={{ Math.random() }}", True)):
            with self.subTest(key=key):
                node = {"name": "Upsert", "type": "n8n-nodes-base.postgres",
                        "retryOnFail": True, "parameters": {"operation": "upsert",
                        "columns": {"matchingColumns": ["id"], "value": {"id": key}}}}
                rules = {f["rule"] for f in review({"nodes": [node]})}
                self.assertEqual("RETRY_WRITE" in rules, expected)

    def test_reject_missing_nodes(self):
        for workflow, expected in (({"nodes": [], "connections": {}}, 0), ({"unrelated": True}, 2)):
            with self.subTest(expected=expected), TemporaryDirectory() as temp:
                path = Path(temp) / "fixture.json"
                path.write_text(json.dumps(workflow))
                result = subprocess.run([sys.executable, str(SKILL / "review.py"), str(path)],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, expected)

    def test_github_workflow_command_escaping(self):
        cases = (
            ("control.json", "Write", "control.json", "Write"),
            ("file%,part:1.json", "Write", "file%25%2Cpart%3A1.json", "Write"),
            ("lines.json", "Write 10%\r\nnext line", "lines.json", "Write 10%25%0D%0Anext line"),
        )
        for filename, name, encoded_file, encoded_name in cases:
            with self.subTest(filename=filename), TemporaryDirectory() as temp:
                path = Path(temp) / filename
                node = {"name": name, "type": "n8n-nodes-base.httpRequest",
                        "parameters": {"method": "POST"}, "retryOnFail": True}
                path.write_text(json.dumps({"nodes": [node], "settings": {"errorWorkflow": "123"}}))
                result = subprocess.run([sys.executable, str(SKILL / "review.py"), str(path),
                                         "--format", "github"], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1)
                lines = result.stdout.rstrip("\n").split("\n")
                self.assertEqual(len(lines), 1)
                line = lines[0]
                self.assertIn(f"/{encoded_file},title=n8n-reliability RETRY_WRITE::", line)
                self.assertIn(f"[{encoded_name}]", line)


if __name__ == "__main__":
    unittest.main()
