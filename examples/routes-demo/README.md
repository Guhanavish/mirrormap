# Route Atlas fixture

Run `python -m projectmirror routes examples/routes-demo` from the MirrorMap checkout.

Expected static route *candidates*:

- Next.js-style dashboard page at `/dashboard` (path convention only)
- Next.js-style handler path `/api/health` (path convention only)
- FastAPI `GET /status` decorator (declaration only)

None of these candidates proves the endpoint is reachable, imported into a running app, or correct. MirrorMap never executes the source.
