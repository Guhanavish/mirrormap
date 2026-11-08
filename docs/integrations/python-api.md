# Python SDK — read-only audit orchestration

The lightweight Python API provides the same evidence-backed pipeline without requiring an agent. Install from a checked-out repository while publishing to a package index is still pending:

```bash
python -m pip install -e .
```

Then:

```python
from projectmirror.experience import audit_project

result = audit_project(
    repo="/path/to/project",
    spec="/path/to/project/docs/requirements.md",
    mode="deep",
    spec_approved=True,  # only after explicit user approval
    out="/tmp/mirrormap-report",
)
print(result["counts"])
print(result["directory"])
```

The API imports real reviewed links using `links=...`, test evidence using `verification=...`, and scoped absence records using `absence=...`. Do not generate these inputs from guesses.

Output files are written outside the audited repository. The API never runs user code or handles production deployment. Errors are raised as `AuditError` for invalid audit requests. Treat other exceptions as ordinary programming errors.
