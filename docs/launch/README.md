# MirrorMap launch kit

These materials are a **distribution kit**, not claims of popularity, endorsements, or a completed external launch. They are based on the real v0.4.0 beta and its intentionally incomplete demo fixture. No external community post is sent automatically.

## Choose the right starting point

| Goal | Resource |
|---|---|
| See the actual demo and its evidence limitations | [30-second demo script](demo-script.md) |
| Publish the first official prerelease | [Release notes and checklist](release-v0.4.0-beta.md) |
| Fix GitHub discovery settings | [Repository metadata](metadata.md) |
| Share outside GitHub responsibly | [Copy-ready posts](community-posts.md) |
| Plan small weekly launch experiments | [30-day plan](30-day-plan.md) |
| Know whether people are using it | [Measurement guide](measuring.md) |

## Three honest messages

1. MirrorMap **compares approved intent, actual source, and observed test evidence**. It does not infer missing requirements from the source code.
2. The v0.4 core CLI is **read-only**, with an interactive local dashboard; it does not execute applications or repair projects itself.
3. Structural scanning and unreviewed test results are **candidates**, not proof that features work or fail.

## Avoid

- Exaggerated claims such as “finds every bug,” “10x development,” or “guaranteed production ready.”
- Asking communities to upvote or star the project, paid/automated star campaigns, or reposting identical promotional messages indiscriminately.
- Reporting install counts until a real installation has been observed.
- Announcing a GitHub Release or a hosted demo before those endpoints are actually live.

For the current product, start with feedback from three developers who can reproduce the demo and make one improvement based on their experience.

## Finish publishing

- [Activate the prepared GitHub Pages branch](pages-setup.md) — repository owner settings required
- [Official beta release notes](release-v0.4.0-beta.md) — the publishing workflow builds and publishes verified assets
- [Animated preview](../../assets/mirrormap-demo-preview.webp) and [30-second MP4](../../assets/mirrormap-30s-demo.mp4)

The beta release workflow is intentionally one-shot on first merge into `main` (or via a manual dispatch). It runs tests and builds release artifacts before publishing.
