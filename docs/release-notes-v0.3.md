# MirrorMap v0.3.0 beta — Route Atlas

The v0.3 update improves discoverability and source-level project inventories without weakening the original evidence-first model.

## Shipped in v0.3

- Next.js App Router and Pages Router **path-convention candidates** in `implementation-map.json`.
- FastAPI **literal decorator candidates** where source explicitly imports FastAPI.
- `python -m projectmirror routes PATH` for portable source-only JSON inventories.
- A repository-local reusable GitHub composite action that saves output under the runner's temporary directory.
- A PR workflow example with minimal permissions and artifact retention.
- 54 automated tests across the CLI, comparison rules, route candidates, and documentation.

## Not shipped

Automatically verified HTTP routes, full TypeScript AST parsing, semantic acceptance-criterion matching, self-running browser tests, a hosted dashboard, direct project edits, automated approval, or guaranteed compatibility with every agent host.

Read [framework route limitations](guides/framework-routes.md) and [GitHub Action instructions](integrations/github-action.md).
