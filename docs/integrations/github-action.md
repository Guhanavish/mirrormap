# MirrorMap GitHub Action — structural PR auditing

The repository ships a **composite** action (`action.yml`) that invokes MirrorMap directly using the bundled Python sources. The action is **read-only with respect to the checked-out project**: it scans files, writes audit artifacts to a fresh folder under `RUNNER_TEMP`, and never executes project application code, creates comments, changes requirements, or applies fixes.

## Quick start

Copy [the workflow example](../../examples/github-actions/mirrormap-composite-audit.yml) to `.github/workflows/mirrormap-pr.yml` in **your own project**, then adjust the spec location and reviewed baseline ref. For production, pin `uses: Guhanavish/mirrormap@<full-commit-sha>` to a revision you have inspected rather than tracking `main`.

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false
    fetch-depth: 0
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
- id: mirrormap
  uses: Guhanavish/mirrormap@main # Replace with a reviewed commit SHA.
  with:
    mode: pr
    base: origin/main
    spec: docs/requirements.md
    approved-spec: 'false'
```

Upload `steps.mirrormap.outputs.report-directory` with `actions/upload-artifact@v4`; the complete workflow demonstrates this even on failures. The action has no special API token requirements, and the example grants only `contents: read`.

## Inputs and capabilities

| Input | Default | Meaning |
|---|---|---|
| `mode` | `quick` | Same modes as the CLI; PR mode provides changed-file *context*, not a semantic impact assessment |
| `spec` | unset | Optional requirement document within the checked-out repository; can also be an absolute path |
| `approved-spec` | `false` | Must be set to `true` **only** after a person has actually approved the requirement document |
| `base` | unset | Git ref for `pr` mode's changed-file inventory; fetch history first |
| `junit` | unset | Existing JUnit XML file/directory **inside** `GITHUB_WORKSPACE`; does not run tests |
| `test-map` | unset | Explicitly reviewed JUnit→criteria mapping; requires `junit`; revision must match Git HEAD |

**Output:** `report-directory`, an absolute ephemeral path containing `dashboard.html`, `findings.json`, `audit-report.md`, `mindmap.mmd`, and other report files.

This action intentionally **does not** auto-review evidence links or fail the job just because requirements remain `unknown`. To get verified conclusions, collect real tests and provide reviewed requirement-to-implementation links and observation records separately. The action can import existing JUnit reports, but never runs test suites or auto-approves mappings.

## Safety and scope

- PR code is untrusted. The action reads checked-out source files as data and **does not execute them**. Use the normal `pull_request` event, not privileged `pull_request_target` to run untrusted PR code.
- The action does not install project dependencies. It uses the checked-out project's `GITHUB_WORKSPACE` and the action package's own Python sources through `PYTHONPATH`.
- Reports can contain source paths and requirement titles. Review them before sharing publicly.
- `mode: visual` does not launch a browser; browser verification is a separate, explicitly authorized integration.
- For an initial run without approved requirements, leave `approved-spec: 'false'` or omit the specification entirely. A structural audit is still useful, but no runtime correctness claims are made.
