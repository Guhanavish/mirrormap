# Contributing to ProjectMirror

Thanks for helping make agent auditing more reliable and transparent.

## Local development

```bash
python -m unittest discover -s tests -v
python -m projectmirror --help
```

Use Python 3.10+ and keep the default audit engine dependency-free. Every bug fix should include a regression test; security- and permission-related changes require tests for both allowed and denied paths.

## Pull requests

- Explain the problem and how to reproduce it.
- Keep the core rule: **no application changes without explicit user approval**.
- Document scope, assumptions, and evidence quality.
- Include tests, examples and behavior changes.
- Avoid adding dependencies to the core CLI unless essential.

## Good first contributions

File-type-specific, read-only scanners with appropriate fixture tests; status visualization improvements; test-result importers; GitHub Actions evaluation fixtures; accessible reporting. Optional MCP adapter work should preserve the same approval contract.

## Reporting vulnerabilities

Do not post secrets, exploit payloads involving real users, or private repository content in public issues. Contact the repository maintainer through GitHub's private vulnerability-reporting feature if enabled.
