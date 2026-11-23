# n8n-reliability

A Claude skill that statically reviews exported n8n workflows for duplicate writes, silent failures and missing error alerts. See SKILL.md for details.

    python3 review.py workflow.json
    python3 review.py workflow.json --format json   # or --format github for CI annotations
    python3 tests/test_pairs.py               # 4 red/green fixture pairs
    python3 tests/test_review_regressions.py  # 8 more pairs: header really sent, stable keys, dedupe on every path, onError precedence

The fixtures are synthetic.

Want it fixed? https://guraforge.com
