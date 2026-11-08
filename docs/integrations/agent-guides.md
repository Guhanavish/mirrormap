# Agent integration patterns

The canonical [SKILL.md](../../SKILL.md) is the source of the audit protocol; do not maintain divergent instructions in every agent.

| Host | Suggested setup | Status |
|---|---|---|
| Claude Code | Copy skill to configured skills directory; Python 3.10+ required for bundled CLI | Manual instructions; test per installation |
| Codex | Copy skill to configured skills directory, use `python -m projectmirror` | Manual instructions; test per installation |
| Other Agent Skills clients | Point to the root `SKILL.md`; verify command execution capability | Generic, not certified |
| MCP clients | Register `python -m projectmirror mcp` with allowlisted roots | Experimental |
| CI / non-agent tooling | Use CLI or Python API; no model required | Supported structural auditing |

### Recommended agent prompt

> Use MirrorMap to inspect this repository. Use the reviewed requirements as intent, inventory real implementation and available verification evidence, prepare a map and a report, and present a prioritized plan. Do not claim unverified features are missing. Stop and request explicit permission before changing project files or running untrusted application tests.

See [installation](../getting-started.md) for a conservative non-overwriting skill installation workflow.
