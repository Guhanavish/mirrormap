# 30-second MirrorMap walkthrough (real fixture, no invented findings)

For a copy-and-paste explanation of both phases, see the [two-minute first-audit guide](../guides/first-audit-walkthrough.md).

This repository includes `assets/mirrormap-30s-demo.mp4` and its animated teaser `assets/mirrormap-demo-preview.webp`. The video is an **edited six-scene storyboard** using real CLI outputs and an authentic previous Chromium dashboard capture. It is **not** an uncut live screen recording.

| Time | Scene | Claim backed by repository behavior |
|---|---|---|
| 00:00–00:05 | The three separate evidence views | Intent, implementation, verification are independent inputs |
| 00:05–00:10 | Real CLI syntax | The command runs a read-only demo with approved fixture requirements |
| 00:10–00:15 | Authentic offline dashboard capture | The initial scan reports three unknown requirements |
| 00:15–00:20 | Reviewed fixture links and absence | A separate sample run reports one missing and two unverified |
| 00:20–00:25 | Review-only plan | The CLI cannot automatically change application files |
| 00:25–00:30 | Project repository link | Source: github.com/Guhanavish/mirrormap |

## Reproduce the story

```bash
python -m projectmirror audit examples/demo-app \
  --spec examples/demo-app/requirements.md --approved-spec --mode deep

python -m projectmirror audit examples/demo-app \
  --spec examples/demo-app/requirements.md --approved-spec --mode deep \
  --links examples/fixture-reviewed-links.json \
  --absence examples/fixture-reviewed-absence.json
```

Use the `--approved-spec` flag only for this deliberately prepared fixture or a real user-approved spec. Neither run executes application code.

## Publishing guidance

- Embed the animated WebP in the README and link it to the 30-second MP4.
- If posting to a video platform, use captions and label the walkthrough as a demonstration fixture.
- Do not say the video proves browser testing or automatically found a production vulnerability.
