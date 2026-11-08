# Getting started with MirrorMap

MirrorMap is an **evidence-backed project auditor**, not an automatic code fixer. It reads source structure, keeps requirements independent, and produces reports **outside** your repository. It does not execute the project's code.

## Choose an entry point

| Goal | Entry point |
|---|---|
| Explore an unfamiliar repository | `python -m projectmirror audit /path/to/repo` |
| Compare against requirements | `python -m projectmirror audit /path/to/repo --spec /path/to/requirements.md --approved-spec` |
| See the original composable CLI | `python -m projectmirror --help` |
| Run from another Python program | `from projectmirror.experience import audit_project` |
| Expose read-only tools to an agent | [Experimental MCP server](integrations/mcp.md) |
| Audit a PR in CI | [GitHub Actions example](../examples/github-actions/README.md) |

`--approved-spec` means **you have already approved the spec**. Omitting it marks imported Markdown requirements draft. No feature will be labeled missing just because the scanner did not find a similarly named symbol.

## Run your first project audit

```bash
git clone https://github.com/Guhanavish/mirrormap.git
cd mirrormap
python -m projectmirror doctor
python -m projectmirror audit ./examples/demo-app --spec ./examples/demo-app/requirements.md --approved-spec --mode deep
```

The command prints the **absolute output directory**. Inspect `dashboard.html` locally, then check `audit-report.md` and `remediation-plan.md` for evidence and next steps. A generated plan is not authorization to modify code.

## Use with an agent

Install a portable copy into your selected skills directory using an explicit destination:

```bash
# Preview; this writes nothing
python -m projectmirror install-skill --dest ~/.codex/skills/mirrormap
# Apply only when the destination is new and you're satisfied
python -m projectmirror install-skill --dest ~/.codex/skills/mirrormap --apply
```

For Claude Code, use your configured Claude skills directory (often `~/.claude/skills/mirrormap`) instead. The installer does **not** overwrite existing directories or edit agent configuration. Restart or reload your agent if its skills directory is scanned only on startup. The package is designed for Python 3.10+; use a compatible interpreter in the agent environment.

You can also try the external [skills CLI](https://skills.sh/) with `npx skills add Guhanavish/mirrormap`; check its current rules and destination options before using it. This is an **external installation path**, not a tested guarantee of detection in every host.

## Where the evidence comes from

- **Intent**: reviewed requirement IDs and acceptance criteria.
- **Implementation**: real scanned files and symbols.
- **Verification**: test or browser observations supplied by a trusted host/reviewer, tied to the current project revision.

The CLI does not magically validate application behavior. Without reviewed requirement-to-implementation links, results should usually be `unknown`, not `missing`. Its suggested links are **hints only**, never findings.

Learn more in [audit modes](guides/audit-modes.md), [MCP](integrations/mcp.md), [Python API](integrations/python-api.md), and [security policy](../SECURITY.md).


## Route discovery and CI

Use `python -m projectmirror routes /path/to/project` for read-only Next.js/FastAPI route **candidates**, not verified endpoints. See [the route fixture](../examples/routes-demo/README.md) and [framework limitations](guides/framework-routes.md). For pull-request inventories, see the [reusable GitHub Action](integrations/github-action.md).
