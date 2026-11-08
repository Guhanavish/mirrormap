# GitHub repository discovery settings

**Repository**: <https://github.com/Guhanavish/mirrormap>

The GitHub contents connector does **not** have permission to edit repository About metadata, topics, Discussions or release settings. These need to be changed by the repository administrator in GitHub's web interface or through a separately authorized administrative workflow.

## About → Edit details

**Description (copy and paste):**

> Open-source AI agent skill to map requirements, examine code and tests, visualize evidence, and plan user-approved fixes.

**Homepage:** `https://guhanavish.vercel.app/` (the creator's portfolio, **not** a hosted MirrorMap demo). Update this to a dedicated MirrorMap URL if one becomes available.

**Topics:**

`agent-skills`, `ai-agents`, `coding-agent`, `developer-tools`, `code-audit`, `spec-drift`, `python`, `mindmap`, `open-source`, `software-quality`

Steps: open the repository, click the gear next to **About**, paste the description/homepage, enter up to 20 topics, then save. Topics should describe present capabilities rather than planned features.

## Community settings

Optionally enable **Discussions** under **Settings → General → Features** to accept community questions and examples. You can use Issues until Discussions is enabled.

## Official prerelease

Use **Releases → Draft a new release**. Create tag `v0.4.0-beta` targeting the reviewed main commit, mark it **pre-release**, then paste the prepared release notes from `docs/launch/release-v0.4.0-beta.md`. Attach tested source ZIP and wheel only after validating them for that exact revision. The README's version badge is not proof that a GitHub Release exists.

## Site deployment

The static, framework-free landing page is in `site/index.html`. It is currently repository source; publishing it requires GitHub Pages or another configured host. Do not advertise a hosted MirrorMap dashboard until such a service is actually deployed.

The static site branch is now prepared: [activate GitHub Pages from the gh-pages branch](pages-setup.md) before adding a hosted URL to the repository.
