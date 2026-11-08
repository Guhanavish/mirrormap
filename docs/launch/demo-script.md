# A truthful 30-second walkthrough

This is a recording script you can reproduce yourself from the bundled demo. **No live screen recording is claimed to be hosted here.** A 30-second edited MP4 and animated preview are available in the separate downloadable project launch archive, while the repository already includes a genuine Chromium screenshot at [assets/mirrormap-interactive-atlas.webp](../../assets/mirrormap-interactive-atlas.webp).

| Time | What to show | What it establishes |
|---|---|---|
| 0–5s | MirrorMap's three evidence layers | Intent, implementation and verification are separate |
| 5–10s | Run the bundled demo command | It scans structural source data |
| 10–15s | Open offline dashboard.html | Three initially unknown requirements; not automatic bugs |
| 15–20s | Import explicitly reviewed sample links and absence claim | Sample audit reports one missing and two unverified |
| 20–25s | Open the review-only remediation plan | The CLI does not change application files |
| 25–30s | Show project URL and invitation to reproduce | github.com/Guhanavish/mirrormap |

### Reproduce the initial audit

From the repository root:

    python -m projectmirror audit examples/demo-app --spec examples/demo-app/requirements.md --approved-spec --mode deep

For the reviewed example:

    python -m projectmirror audit examples/demo-app --spec examples/demo-app/requirements.md --approved-spec --mode deep --links examples/fixture-reviewed-links.json --absence examples/fixture-reviewed-absence.json

Use the approved-spec flag on a real project only if its specification truly has been approved by the user. No application source is executed by these commands.

### Recording best practices

Show the actual commands, the full results, and the limits on each screen. Use captioned screen capture, trim idle time and export an optimized MP4/WebP teaser. Avoid any claim that the demo proves comprehensive security auditing or automatically repairs a production app.
