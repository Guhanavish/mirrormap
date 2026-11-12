# Verified Skills CLI install: Codex, clean GitHub runner

MirrorMap provides a portable `SKILL.md` and a separate Python audit CLI. **Installing the skill does not install the Python package or prove a Codex agent can autonomously perform a full audit.** The guide documents precisely what has been verified.

## Confirmed reproducible installation

The [GitHub Actions clean-install job](../../.github/workflows/skills-install-smoke.yml) previously passed in [run 42490945191](https://github.com/Guhanavish/mirrormap/actions/runs/42490945191). Its logs reported:

| Property | Observed value |
|---|---|
| Runner | GitHub-hosted `ubuntu-latest` / Linux x64 |
| Node.js | `v22.20.0` |
| npm | `10.9.3` |
| Installer | `skills@1.7.6` |
| Target agent | `codex` |
| Selected skill | `mirrormap` |
| Installation mode | `--copy`, no global user configuration |
| Installed file | `.agents/skills/mirrormap/SKILL.md` in a disposable directory |
| Result | Installer found one skill and copied it; SKILL.md was nonempty and identified itself as MirrorMap |

To reproduce in an **empty, disposable** directory on a supported system:

```bash
mkdir mirrormap-install-check
cd mirrormap-install-check
npx --yes skills@1.7.6 add Guhanavish/mirrormap --skill mirrormap -a codex --copy -y
# Verify this exact file exists and contains MirrorMap instructions:
# .agents/skills/mirrormap/SKILL.md
```

Check the current [Skills CLI documentation](https://skills.sh/docs) before using an unpinned version or different agent. On Windows, use `New-Item -ItemType Directory mirrormap-install-check` followed by `Set-Location mirrormap-install-check`; file paths use Windows separators.

## Verify the *separate* Python audit tool

From a clone of the MirrorMap repository, with Python 3.10+:

```bash
python -m projectmirror doctor
python -m projectmirror audit examples/demo-app \
  --spec examples/demo-app/requirements.md --approved-spec --mode deep
```

The expected fixture result is `{"unknown": 3}`. If you import the reviewed fixture links and scoped absence confirmation, the expected result is `{"missing": 1, "unverified": 2}`. Follow the [two-minute walkthrough](../guides/first-audit-walkthrough.md) for complete commands and interpretation.

## What this does **not** validate

- A live, interactive Codex agent session detecting and loading the skill on demand.
- The skills installation location or behavior of Claude, Cursor, other agents, or different operating systems.
- Python execution by the skill installer alone; it installs instructions and references, not the separate Python CLI.
- Full semantic verification or automatic code changes.

For additional agents or OS platforms, submit reproducible sanitized logs and environment details in a PR. Do not include passwords, tokens, personal paths or private source. Re-run the clean-install workflow when changing `SKILL.md`, the installer instructions, or this document.
