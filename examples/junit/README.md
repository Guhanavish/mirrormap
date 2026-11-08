# Import JUnit evidence without running tests

This deliberately small JUnit XML fixture demonstrates one passing, one failing, and one skipped test. It is **illustrative input** and not evidence of a real project deployment. The reader must independently review whether a particular test asserts the named acceptance criterion.

```bash
python -m projectmirror audit examples/demo-app \
  --spec examples/demo-app/requirements.md --approved-spec --mode deep \
  --junit examples/junit/sample-results.xml
```

Open the generated `junit-candidates.json` and interactive `dashboard.html`. The audit remains `unknown`: no test-to-requirement mapping has been approved, and the demo app is unversioned.

To promote **real** tests to verification evidence: (1) work in a Git repository with a valid current commit, (2) supply a reviewed test-to-criterion mapping, (3) set `revision` to the exact revision those tests actually exercised, (4) provide separately reviewed implementation links, and (5) rerun the audit. The mapping template is a *schema example*, not pre-approved evidence. A test report's outcome and asserted revision are not independently attested by MirrorMap.

See [JUnit evidence guide](../../docs/guides/junit-evidence.md).
