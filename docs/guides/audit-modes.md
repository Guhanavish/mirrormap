# Audit modes and evidence levels

MirrorMap offers several entry-point modes. The **actual evidence available**, rather than a mode's name, determines what can be asserted.

| Mode | Command | What is actually performed in v0.2 | Not automatically performed |
|---|---|---|---|
| Quick | `--mode quick` | Read-only structural inventory, optional requirement comparison, reports | Behavioral tests |
| Deep | `--mode deep` | Full available structural inventory, candidate-link hints, evidence-backed diff | Semantic verification without reviewed evidence |
| PR | `--mode pr --base origin/main` | Inventory plus Git changed-file list | Automatic affected-requirement or regression proof |
| Drift | `--mode drift --baseline /old/audit` | Current audit plus comparison of prior finding classifications | Proof that changes are regressions |
| Visual | `--mode visual` | Structural audit and optional imported verification | Browser launch/screenshots without external host tools |

## Example: compare a project with requirements

```bash
python -m projectmirror audit ./app \
  --spec ./app/docs/requirements.md \
  --approved-spec \
  --mode deep \
  --out /tmp/mirrormap-app
```

Inspect `candidate-links.json` and **review source locations manually** before building a valid `links.json` with your agent. Do not copy heuristic candidates directly into reviewed links. When you have actual tests or browser evidence, use `--verification` with a valid verification map and the current revision.

## PR mode

```bash
python -m projectmirror audit . --mode pr --base origin/main --out /tmp/mirrormap-pr
```

The `pr-scope.json` file contains changed paths if the Git base can be resolved locally. It is a helpful scope hint, **not a claim of complete impact analysis**.

## Drift mode

```bash
python -m projectmirror audit . --spec docs/requirements.md --approved-spec \
  --mode drift --baseline /tmp/prior-mirrormap-audit --out /tmp/current-mirrormap-audit
```

`baseline-diff.json` lists classification changes and missing/new IDs. Prior and current audits must use equivalent requirement sources for meaningful comparisons. Change alone does not prove a regression.

## Visual mode

The optional host agent (e.g. a browser-equipped coding agent) must separately **obtain permission** for runtime probing, collect and review observations, and save valid verification records. Without them MirrorMap clearly reports that no browser checks occurred.

## Outputs

Every standard audit generates `implementation-map.json`, `intent-map.json`, `findings.json`, `plan.json`, `audit-manifest.json`, `audit-report.md`, `remediation-plan.md`, `mindmap.mmd`, and an offline `dashboard.html` file. When the spec exists, `candidate-links.json` also appears.
