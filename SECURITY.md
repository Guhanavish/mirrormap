# Security policy

ProjectMirror is an experimental development tool, **not** an enforcement sandbox. Audit outputs are written outside the inspected repository by the command-line workflow. The CLI avoids reading typical credential files and does not execute project code or authorize edits. Those controls reduce risk but are not a substitute for host-level filesystem, process, network, and permission boundaries.

## Current limitations

- It cannot authenticate a human approval receipt: `check-approval` checks only consistency.
- Its source index is structural, not a proof of completeness or correctness.
- The secret-file exclusion list is conservative but not exhaustive.
- Runtime checks require external tools and an explicitly safe environment.

To report a vulnerability, use GitHub's private vulnerability reporting where available. Do not include live credentials, sensitive code, or production data in a public issue.
