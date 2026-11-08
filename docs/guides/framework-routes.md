# Static route inventory (experimental)

MirrorMap can now discover **candidate** web routes in source files using low-cost structural rules. No web application is started, imported, or queried.

```bash
python -m projectmirror routes /absolute/path/to/your-repo
# Or generate an entire audit, whose implementation-map.json includes route candidates:
python -m projectmirror audit /absolute/path/to/your-repo --mode deep
```

## Recognized declarations

| Framework style | Recognition | What is *not* proven |
|---|---|---|
| Next.js App Router | `app/**/page.{js,jsx,ts,tsx}` and `app/**/route.{js,jsx,ts,tsx}`, including `src/app` | Route registered, page rendered, handler methods, server runtime |
| Next.js Pages Router | Files beneath `pages/` or `src/pages/`, with `pages/api` marked as handler candidates | Whether the project even uses Next.js or exports are valid |
| FastAPI | Literal-path `@app.get('/...')`, `@router.post('/...')`, etc. in Python files that directly import FastAPI | Router included, middleware, dependencies, response or authentication behavior |

Route candidates have `kind: route_candidate`, a deterministic ID, source locator and evidence link, inferred path and framework declaration label. Confidence is `path_convention_only` or `declaration_only`.

This is **not a framework-aware runtime verifier**. Ambiguous dynamic Python routes, unusual segment syntax, runtime-generated registrations and most other frameworks remain undiscovered. The CLI never converts a discovered candidate into a reviewed requirement mapping or a test pass automatically.

## When to use

Use this to orient an agent quickly in a Next.js or FastAPI repository, suggest areas to inspect, and find route declarations for human review. For verified user journeys, run isolated tests or browser probes with the explicit permissions and tooling of the host agent; import only actual observations.
