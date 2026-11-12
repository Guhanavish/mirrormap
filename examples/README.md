# Demonstration project

**New to MirrorMap?** Start with the [reproducible two-phase walkthrough](../docs/guides/first-audit-walkthrough.md): first 3 `unknown`, then 1 `missing` and 2 `unverified` with reviewed **fixture** evidence.

`demo-app/` is intentionally incomplete. Its Python code must **not** be used for authentication; it exists to demonstrate that file discovery alone cannot establish correctness.

Use the command sequence in `references/workflow.md`. Without reviewed links, real test evidence, or absence confirmations, the audit will responsibly show **unknown** rather than pretending it found missing/working features.

To see complete deterministic behavior, run `python -m unittest discover -s tests -v`: the test suite builds synthetic reviewed links and verification facts and checks the resulting classifications.

### Optional: demonstrate reviewed gap classifications

The repository includes **reviewed example fixtures** for two implementation links and one absence confirmation. These fixtures apply only to this tiny sample app; do not reuse them as evidence for a real project.

After the basic walkthrough, run:

```bash
python -m projectmirror link --from examples/fixture-reviewed-links.json --out /tmp/projectmirror-demo
python -m projectmirror absence --from examples/fixture-reviewed-absence.json --out /tmp/projectmirror-demo
python -m projectmirror diff --out /tmp/projectmirror-demo
python -m projectmirror plan --out /tmp/projectmirror-demo
python -m projectmirror render --out /tmp/projectmirror-demo
```

Expected result: **2 unverified** feature implementations and **1 missing** recovery feature (based on the sample's explicit reviewed absence claim). A present login function is **not** considered correct authentication without current passing test evidence.
