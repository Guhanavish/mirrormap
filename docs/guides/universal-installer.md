# MirrorMap Universal Installer (preview)

The setup manager installs the bundled skill and configures project-filtered user-level Relay hooks. Eco mode and metadata-only recording are the defaults. It requires explicit approval before changing settings. It never automatically changes global PATH or bypasses a host sandbox.

## If Python already works

Install the engine from a reviewed source checkout or with pip:

    py -m pip install --upgrade git+https://github.com/Guhanavish/mirrormap.git
    py -m projectmirror setup --agent codex --project .
    py -m projectmirror setup --agent codex --project . --apply

Use python3 instead of py on macOS/Linux. You do not need the separate Skills CLI command. The engine must be installed in the interpreter, not merely importable from the current source directory, because hooks use isolated Python mode.

Use setup --wizard for an interactive terminal, --auto to select detected local agents, or repeat --agent for several agents. Use --capture-context only with informed consent for bounded redacted excerpts. Select --mode eco, balanced, detailed or manual. Review the printed plan before --apply.

## Without Python

The [standalone installer preview release](https://github.com/Guhanavish/mirrormap/releases/tag/installer-preview-1) is published after all four native build/smoke checks and source regression tests passed. Download the Windows x64 EXE directly from that release. There is no published npm package named mirrormap from this repository. If a browser reports a blocked executable or a security warning, inspect the exact warning and verify the source and checksum; do not bypass security policy.

Download the appropriate executable and SHA256SUMS.txt from the GitHub release installer-preview-1. Verify the exact asset hash before running. The assets are unsigned native CLI executables, not signed MSI, PKG or graphical installers. Do not bypass Windows/macOS security policy.

Windows x64:

    .\mirrormap-windows-x64.exe setup --wizard

Linux x64:

    chmod +x mirrormap-linux-x64
    ./mirrormap-linux-x64 setup --wizard

macOS Intel / Apple Silicon: use mirrormap-macos-x64 / mirrormap-macos-arm64 respectively. Other architectures can use Python installation. Git is still needed for reliable Git workspace fingerprinting. Native binaries include the Python runtime and optional encryption support; no separate Python or Node installation is required.

The setup manager copies the native executable into a hash-named directory under ~/.mirrormap/bin. Hooks reference that absolute path, not the temporary download. Use the exact engine invocation reported by setup or ~/.mirrormap/installation.json for subsequent CLI commands.

For Windows, scripts/install.ps1 can download and verify the native asset using built-in PowerShell tools. Download and review the script before running it:

    .\install.ps1 -Agent codex -Project . 
    .\install.ps1 -Agent codex -Project . -Apply

On macOS/Linux, download and review scripts/install.sh, then run:

    sh install.sh setup --agent codex --project .
    sh install.sh setup --agent codex --project . --apply

For Node.js 20+ with Git and network access, the GitHub-distributed bootstrap can be invoked as follows:

    npx --yes --package github:Guhanavish/mirrormap#main mirrormap-bootstrap setup --agent codex --project . --apply

This is a GitHub package invocation, not an npm registry publication. The bootstrap is pinned to the installer-preview-1 release tag, validates SHA256SUMS.txt before launching, and stops on failed downloads/checksums. The hashes protect against accidental corruption, not compromise of the release account. Pin a reviewed source commit instead of main for reproducible bootstrap code.

## Diagnose, repair and update

Replace ENGINE with the full invocation printed by setup (for example, py -m projectmirror or the absolute native executable path).

    ENGINE installation-doctor --project .
    ENGINE repair --project .
    ENGINE repair --project . --apply
    ENGINE update --project . --apply
    ENGINE uninstall --project . --apply

Repair restores the setup manager's own hooks. Update switches managed hooks and owned skill files to the currently running, explicitly installed engine; it is not an automatic network updater. Get a newer verified executable or wheel first. Uninstall removes managed hooks and their installation entries only; it retains skill files, executable files and local Relay/BOLT records to avoid destructive data loss. Existing third-party or manually installed skill directories are not overwritten; update them using their original installer. Older hooks installed directly with a different Python interpreter may require separate removal using that interpreter. No broad command-string matching or deletion is used.

The manager records exact hook commands and skill hashes in ~/.mirrormap/installation.json. If interrupted while applying, inspect the settings and rerun repair; an existing installation.lock directory prevents concurrent setup manager writes. Direct edits by other programs remain outside this lock.

## Host approval and restricted environments

The installer cannot guarantee the host has delivered a hook. Restart/reload the agent and review/trust its hooks in the native UI. Verify a real session appears in Relay sessions before depending on automatic recovery.

If an agent reports that Python and mirrormap are unavailable, check the actual execution environment. Local Windows installation cannot install software in an isolated remote Linux environment. Run the approved bootstrap locally in that environment if permitted, or use the skill-only instructions. Do not attempt to evade sandbox restrictions or network policy.

Skill-only fallback: ask the agent to compare requirements, implementation and evidence using its own read-only tools and manually save a reviewed brief. BOLT/Relay persistence, hook delivery and cryptographic packages are unavailable without a functioning engine. Never claim these ran.
