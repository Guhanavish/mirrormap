# Automatic collection of existing JUnit XML reports

MirrorMap v0.4 adds **opt-in JUnit XML ingestion**. It parses existing files; it does not invoke pytest, Jest, Maven, your project, or any arbitrary command. This is evidence collection, **not automatic test generation or semantic test interpretation**.

## Read-only first pass

```bash
python -m projectmirror audit /absolute/path/to/repo \
  --spec /absolute/path/to/repo/docs/requirements.md \
  --approved-spec --mode deep \
  --junit /absolute/path/to/repo/reports/junit.xml \
  --out /tmp/mirrormap-run
```

The report or its parent directory may be passed more than once with `--junit`. Generated `junit-candidates.json` includes each testcase key, observed outcome (`passed`, `failed`, `inconclusive` for skipped), report filename, and SHA-256 file hash. Raw failure tracebacks and test stdout are excluded by design, to reduce accidental log/secret leakage. JUnit XML is parsed only; no tests are run.

**No mapping = no promoted verification records.** This matters: matching test names to features by fuzzy text would manufacture success claims.

## Reviewed mapping

```json
{
  "reviewed": true,
  "revision": "<exact current Git commit SHA>",
  "tests": [
    {
      "key": "tests.Auth::test_login",
      "requirement_id": "REQ.auth.login",
      "criteria_ids": ["AC.auth.login.valid"]
    }
  ]
}
```

The reviewer must check that the test really asserts the cited acceptance criterion, then record the correct revision. The repository's intent specification must contain this requirement and criterion ID. MirrorMap checks mapping uniqueness, IDs, test existence and revision equality; it cannot independently prove test execution provenance, assertion sufficiency, or that the claimed revision was actually tested.

```bash
python -m projectmirror audit /absolute/path/to/repo \
  --spec /absolute/path/to/repo/docs/requirements.md \
  --approved-spec --mode deep \
  --junit /tmp/junit.xml --test-map /tmp/reviewed-junit-map.json \
  --links /tmp/reviewed-code-links.json
```

Only reviewed links and revision-matched acceptance-criterion observations can support a `complete` outcome. A mapped failing observation supports `broken`. If either link or evidence is missing, the result remains `unknown` or `unverified` as appropriate.

## Import after an audit

If a report becomes available later, without rerunning source indexing:

```bash
python -m projectmirror evidence --out /tmp/mirrormap-run --junit /tmp/results.xml
# Optional: --test-map /tmp/reviewed-junit-map.json
python -m projectmirror diff --out /tmp/mirrormap-run
python -m projectmirror plan --out /tmp/mirrormap-run
python -m projectmirror render --out /tmp/mirrormap-run
python -m projectmirror dashboard --out /tmp/mirrormap-run
```

The `evidence` command imports into an initialized output directory and does not regenerate findings until you run `diff`. Duplicate imported IDs are rejected to avoid silent overrides.

## Data and safety boundaries

- Only `.xml` regular, non-symlink report files; DTD/entity declarations rejected.
- Maximum 60 reports, 4 MB each, and 25,000 testcases total.
- No network requests, project code execution, arbitrary shell commands, or repository writes.
- Do not use `reviewed: true` without reviewing each test and criterion.
- A review flag and git SHA are **statements**, not a cryptographic chain of custody. Treat attacker-controlled reports as untrusted.
- JUnit inputs may include sensitive metadata in test names and paths; review output before publishing artifacts in public CI.
- Browser, API, coverage, or log probes require separately permissioned host tools; these sources are not automatically collected in v0.4.
