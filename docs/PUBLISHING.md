# Publish and grow ProjectMirror

This is a release checklist, not a guarantee of traffic or growth.

## GitHub repository setup

- **Repository:** `mirrormap`
- **Visibility:** public
- **Default branch:** `main`
- **Short description:** `Evidence-backed AI agent skill to map requirements, detect spec drift, and plan user-approved fixes.`
- **Suggested topics:** `agent-skills`, `ai-agents`, `spec-drift`, `software-audit`, `mindmap`, `developer-tools`, `python`, `coding-agent`, `human-in-the-loop`, `open-source`
- **Website:** optional; do not add an unrelated URL.
- **License:** MIT (included).

## Publish checklist

1. Run `python -m unittest discover -s tests -v` and `python -m compileall -q projectmirror tests`.
2. Create a new **public** GitHub repository named `mirrormap`. GitHub's starter README and license can be replaced with the release versions. Do not put it in an unrelated existing repository.
3. Publish the repository files and check that the root README, skill metadata, and workflow appear correctly.
4. Check the Actions tab: wait for all Python matrix jobs to finish; repair any platform-version failures before claiming green CI.
5. Add the description and topics, enable Discussions if you want community questions, and configure vulnerability reporting.
6. Cut a pre-release tag `v0.1.0` after successful CI; attach changelog notes and a tested ZIP if useful.
7. Share a small, reproducible demo and explanation of how `unknown` differs from `missing`.
8. Invite issues labeled `good first issue`, showing where language parsers or adapters can contribute.

## Launch message template

> **ProjectMirror v0.1.0** — a portable Agent Skill + Python CLI for evidence-backed spec drift auditing. Instead of asking an agent to guess what's missing, it keeps approved intent separate from code and test evidence, generates a traceable mindmap, and stops before any project edits. The first release is deliberately read-only and experimental. Feedback and scanner contributions welcome.

## Positioning, without misleading claims

Emphasize: independent requirement maps, deterministic classification, explainable unknowns, human approval, open formats, stdlib Python core.

Avoid: “finds every bug,” “fully autonomous,” “zero errors,” “production-certified,” “all agents supported out of the box,” and “automatically patches your live deployment.” Those would not be accurate for the current release.

## Known first-release limitations

The CLI performs **structural** scans. Reviewed mappings, absent-feature confirmations and runtime verification records are separate inputs; it cannot produce reliable full functional audit results from a bare source scan alone. Some scanners are heuristics, schema files are documentation contracts rather than complete runtime validators, and the built-in receipt checker is not an authorization system. The host agent must enforce approval before implementation.
