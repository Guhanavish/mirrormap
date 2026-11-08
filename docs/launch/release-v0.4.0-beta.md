# MirrorMap v0.4.0-beta — Evidence Atlas

An early open-source beta of a **portable Agent Skill + Python CLI** for comparing approved requirements, observed source structure, and independently collected verification evidence. It produces a locally viewable Evidence Atlas and a review-only remediation plan.

## What is included

- Three independently sourced maps: intent, implementation, and verification.
- Local interactive HTML dashboard with navigation, search, filtering, and evidence links.
- Existing JUnit XML report import; a test can satisfy an acceptance criterion only with reviewed mapping and current-revision evidence.
- Source-only candidate route inventory for selected Next.js and FastAPI patterns.
- CLI, portable `SKILL.md`, Python API, experimental local MCP, and read-only GitHub Action.
- An original 30-second illustrative walkthrough using authentic demo fixture outputs.

## Quick start

```bash
git clone https://github.com/Guhanavish/mirrormap.git
cd mirrormap
python -m projectmirror audit examples/demo-app --spec examples/demo-app/requirements.md --approved-spec --mode deep
```

The example contains a **prepared fixture** specification. Do not use `--approved-spec` on your own project without actual approval. Full instructions: [Getting started](../getting-started.md).

## Known limits

MirrorMap does not execute application code, automatically repair features, prove arbitrary behavior through static scanning, or deploy an online dashboard. JUnit reports without reviewed traceability are not used as proof that features pass. Plugin installation on every coding-agent platform has not been independently verified. See [Security and limitations](../../SECURITY.md).

This is an experimental, read-only beta. Feedback and reproducible issues are welcome: https://github.com/Guhanavish/mirrormap/issues
