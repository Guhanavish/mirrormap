# Experimental MCP integration

The built-in server exposes three **read-only** tools over newline-framed JSON-RPC stdio:

- `mirrormap_doctor` — local prerequisites.
- `mirrormap_audit` — inspect only explicitly allowlisted project folders and write outside the project.
- `mirrormap_read_report` — read a generated report for an allowlisted project.

It **cannot** execute application code, deploy, approve plans, or modify inspected files. It is experimental and has not been certified against every agent host. No network listener is started.

## Starting it

```bash
# macOS/Linux example; point this to a folder you trust the agent to inspect
export MIRRORMAP_ALLOWED_ROOTS="$HOME/projects"
python -m projectmirror mcp
```

Use your agent's custom MCP-server UI to register the command with an absolute Python interpreter and the `MIRRORMAP_ALLOWED_ROOTS` environment variable. On Windows, set this environment variable to a full local path and use `python.exe` or the appropriate launcher. Multiple roots are separated using the platform path separator (`:` on Unix, `;` on Windows).

### Example JSON registration shape

```json
{
  "mcpServers": {
    "mirrormap": {
      "command": "python",
      "args": ["-m", "projectmirror", "mcp"],
      "env": {
        "MIRRORMAP_ALLOWED_ROOTS": "/absolute/path/to/trusted/projects"
      }
    }
  }
}
```

**This is an example data shape, not a claim that every client accepts the same config file.** Use the client's current registration instructions. MCP tool calls are read-only with respect to the inspected project, but may generate audit artifacts in a separate output directory. Restrict the server to trusted local agents; output destinations should also be secured by filesystem permissions.

## Compatibility and security

The server supports MCP `initialize`, `ping`, `tools/list`, and `tools/call` for its three tools. It does not currently support streaming progress, prompts, resources, OAuth, or remote transports. It uses the core JSON schema version 1.0. Tool input schemas are intentionally small; unknown arguments should not be used as a way to authorize elevated operations. Ensure you trust the connected agent's tool calls and filesystem permissions.
