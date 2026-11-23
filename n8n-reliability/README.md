# n8n-reliability

A Claude skill that statically reviews exported n8n workflows for duplicate writes, silent failures and missing error alerts. See SKILL.md for details.

    python3 review.py workflow.json
    python3 tests/test_pairs.py   # 4 red/green fixture pairs

The fixtures are synthetic.
