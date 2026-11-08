<div align="center">

<img src="assets/mirrormap-atlas.svg" width="100%" alt="MirrorMap — evidence over assumption. Three independently grounded maps converge into a human-gated audit." />

<br>

**A portable project intelligence skill that separates what you meant, what you built, and what you actually verified.**

[![Tests](https://github.com/Guhanavish/mirrormap/actions/workflows/ci.yml/badge.svg)](https://github.com/Guhanavish/mirrormap/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-29423C?logo=python&logoColor=white)](pyproject.toml)
[![MIT](https://img.shields.io/badge/License-MIT-29423C)](LICENSE)
[![Official beta](https://img.shields.io/badge/Release-v0.4.0--beta-2D6254)](https://github.com/Guhanavish/mirrormap/releases/tag/v0.4.0-beta)
[![Agent Skill](https://img.shields.io/badge/Open_Agent_Skill-SKILL.md-A5D9B4)](SKILL.md)

[![Start Auditing](https://img.shields.io/badge/START_AUDITING-Quick_Start-9AE0BC?style=for-the-badge&logo=python&logoColor=14231C)](#get-a-result-in-one-command)
[![Read the Guide](https://img.shields.io/badge/READ_THE_GUIDE-Documentation-18313A?style=for-the-badge&logo=readthedocs&logoColor=white)](docs/getting-started.md)
[![Creator](https://img.shields.io/badge/CREATOR-Visit_Website-18313A?style=for-the-badge&logo=vercel&logoColor=white)](https://guhanavish.vercel.app/)
[![Contribute](https://img.shields.io/badge/CONTRIBUTE-Open_Source-18313A?style=for-the-badge&logo=github&logoColor=white)](CONTRIBUTING.md)

[**Why it exists**](#why-mirrormap-exists) · [**How it works**](#the-evidence-atlas) · [**Interactive Atlas**](#interactive-evidence-atlas) · [**JUnit evidence**](#import-test-evidence-without-running-code) · [**Audit modes**](#one-engine-five-views) · [**Integrations**](#meet-your-agent-where-it-works) · [**Roadmap**](#roadmap)

</div>

---

## Watch the real 30-second walkthrough

[![MirrorMap demonstration: three independent evidence layers, real local dashboard capture, and reviewed sample findings](assets/mirrormap-demo-preview.webp)](assets/mirrormap-30s-demo.mp4)

**[Watch or download the 30-second MP4](assets/mirrormap-30s-demo.mp4)** · [Follow the reproducible demo script](docs/launch/demo-script.md)

This narrated-by-captions, edited walkthrough uses the **bundled fixture** and an actual captured dashboard image. The initial audit has three **unknown** requirements; after importing **reviewed sample** links and scoped absence evidence, it reports one **missing** and two **unverified**. These are fixture results, **not** a claim of automatic production bug detection or a live uncut recording.

[**Get the verified beta package**](https://github.com/Guhanavish/mirrormap/releases/tag/v0.4.0-beta) · [**Enable the optional static website**](docs/launch/pages-setup.md)

## Install as an agent skill

For agents supported by the independent [Skills CLI](https://www.skills.sh/docs), the standard GitHub install syntax is:

```bash
npx skills add Guhanavish/mirrormap
```

This requires a recent Node.js runtime for the installer (the Skills CLI's current minimum is Node.js 22.20+); MirrorMap's underlying Python CLI separately requires Python 3.10+. **Installation with every individual agent has not been certified**. You can always use the repository directly with `python -m projectmirror`, or install the root [`SKILL.md`](SKILL.md) manually following your agent's instructions. See the [install and integration guide](docs/getting-started.md).

## Why MirrorMap exists

A repository can have a login page and still lack a working login flow. A test can exist without testing the acceptance criteria. And an AI agent can overlook unfinished work because the code itself is the only thing it inspected.

**MirrorMap keeps three kinds of knowledge separate.** It asks what the product promises, what code demonstrably exists, and what independent observations prove—without treating missing search hits as missing features.

| Most code summaries | MirrorMap's approach |
|---|---|
| Tell you what files exist | Link stable requirements to source evidence |
| Treat presence as implementation | Keep tests and acceptance criteria separate |
| Guess missing features | Use `unknown` until scoped absence is reviewed |
| Offer free-form fixes | Produce a review-only, digest-bound plan |
| Depend on one agent | Provide a portable skill, CLI, SDK, and experimental MCP |

## The Evidence Atlas

```mermaid
flowchart LR
    S["Approved requirements"] --> I["01 · Intent"]
    R["Repository inventory"] --> M["02 · Implementation"]
    T["Real observations"] --> V["03 · Verification"]
    I --> C["Evidence-linked comparison"]
    M --> C
    V --> C
    C --> G["Mindmap · Findings · Plan"]
    G --> A{"User approves exact scope?"}
    A -->|No| X["Stop or revise"]
    A -->|Yes| H["External coding agent acts"]
    H --> Z["Re-test and re-audit"]
    classDef first fill:#173a36,stroke:#83c9a9,color:#e9f5ef;
    class I,M,V,C,G first;
```

Every conclusion needs a trail back to source, approved requirements, or verified observations. The pretty mindmap is simply a view of that underlying JSON model.

> [!IMPORTANT]
> **Source scanning is not functional testing.** MirrorMap's core does **not** execute the project's application code, automatically change files, or approve its own remediation. Browser tests and execution require separate host capabilities and permission. v0.4 is a beta, not an exhaustive bug detector.

## Get a result in one command

**Requires Python 3.10+**. The runtime uses the standard library. Run directly from the repository:

```bash
git clone https://github.com/Guhanavish/mirrormap.git
cd mirrormap
python -m projectmirror audit ./examples/demo-app \
  --spec ./examples/demo-app/requirements.md \
  --approved-spec --mode deep
```

The command prints an output directory **outside** the inspected project. Open the new **interactive** `dashboard.html` in your browser or inspect the generated reports. `--approved-spec` is for an *actually approved* spec; the bundled fixture intentionally demonstrates one.

| Generated file | What you'll see |
|---|---|
| `dashboard.html` | Interactive, searchable, zoomable, offline three-layer evidence atlas |
| `audit-report.md` | Classified requirements and rationale |
| `mindmap.mmd` | Mermaid mindmap of findings |
| `candidate-links.json` | Explicitly **unreviewed** possible code matches |
| `remediation-plan.md` | Human-review task proposals; not an execution authorization |
| `audit-manifest.json` | Revision, scope, and known limitations |

Try an inventory without a spec:

```bash
python -m projectmirror audit /path/to/project
```

This is intentionally **structural inventory only**, not a false promise that the tool knows what your app should do.

### An actual demo result

The included intentionally incomplete fixture yields **three `unknown` requirements** when no reviewed implementation links are supplied. That's the correct, conservative answer. See [the worked example](examples/README.md) for importing reviewed links and absence evidence to get a meaningful gap report.

## Interactive Evidence Atlas

Search findings, filter by classification, click graph nodes, zoom the three-lane **Intent → Implementation → Verification** graph, and inspect directly linked evidence without sending project data to a server. The dashboard is an **offline HTML document**, not a hosted tool or execution interface.

![Actual MirrorMap demo audit displayed in Chromium: three unknown requirements with intent, implementation, and verification lanes](assets/mirrormap-interactive-atlas.webp)

<sub>Real capture of the bundled demo project. The requirements are correctly marked **unknown**, not falsely reported as missing. The capture is not a claim that these features passed tests.</sub>

[Interactive atlas guide](docs/guides/interactive-atlas.md) · [Re-render an existing audit](docs/guides/interactive-atlas.md#explore-the-audit)

## Import test evidence without running code

**v0.4** can automatically parse *existing* JUnit XML results, preserving source hashes and case outcomes. No project code or test runner is executed:

```bash
python -m projectmirror audit ./examples/demo-app \
  --spec ./examples/demo-app/requirements.md --approved-spec \
  --mode deep --junit ./examples/junit/sample-results.xml
```

This produces `junit-candidates.json` with observed passes, failures, and skips. **Importing a passing test does not make a feature complete.** The test must be linked to a declared acceptance criterion through an explicitly reviewed mapping at the correct repository revision, and implementation links must also be reviewed. Without that, the result stays unknown/unverified.

[JUnit evidence guide](docs/guides/junit-evidence.md) · [Sample XML and mapping template](examples/junit/README.md)

## One engine, five views

| Mode | Main purpose | Example |
|---|---|---|
| **Quick** | Lightweight source inventory | `--mode quick` |
| **Deep** | Requirements, candidate links, validated evidence | `--mode deep --spec docs/requirements.md` |
| **PR** | Git changed-file context plus audit | `--mode pr --base origin/main` |
| **Drift** | Compare classifications to a prior baseline | `--mode drift --baseline /tmp/prior-audit` |
| **Visual** | Import host-collected visual verification where available | `--mode visual --verification tests-evidence.json` |

The modes share the same evidence rules. **PR mode does not automatically prove regression impact, and Visual mode does not launch a browser by itself.** [Understand every mode and limitation](docs/guides/audit-modes.md).

## Meet your agent where it works

<div align="center">
<table>
<tr><td width="50%"><b>🧠 Agent Skill</b><br>Use <a href="SKILL.md">SKILL.md</a> with Agent Skills-compatible clients; preview installation before copying files.</td><td width="50%"><b>⌨️ CLI</b><br><code>python -m projectmirror audit ...</code> for repeatable inspection and offline reports.</td></tr>
<tr><td><b>🔌 Local MCP (experimental)</b><br>Three allowlisted, read-only tools exposed via stdio JSON-RPC. <a href="docs/integrations/mcp.md">Setup and limits</a>.</td><td><b>🐍 Python API</b><br><code>from projectmirror.experience import audit_project</code> for custom workflows. <a href="docs/integrations/python-api.md">Examples</a>.</td></tr>
<tr><td><b>⚙️ GitHub Actions example</b><br>Generate artifact reports on pull requests; no auto-fixes. <a href="examples/github-actions/README.md">See workflow</a>.</td><td><b>🗺 Offline dashboard</b><br>Self-contained HTML report, generated with the audit. No hosted account needed.</td></tr>
</table>
</div>

**Discover source-level route candidates** (no application execution):

```bash
python -m projectmirror routes examples/routes-demo
# or: python -m projectmirror routes /path/to/your-project
```

The structural adapter recognizes some Next.js file-based routes and Python FastAPI decorator declarations. **These are possible route registrations, not verified endpoints.** [See supported patterns and limitations](docs/guides/framework-routes.md) · [Reproducible example](examples/routes-demo/README.md).

**Check your setup:**

```bash
python -m projectmirror doctor
```

**Install the skill into your agent's configured skills folder** (this is a preview first):

```bash
python -m projectmirror install-skill --dest ~/.codex/skills/mirrormap
python -m projectmirror install-skill --dest ~/.codex/skills/mirrormap --apply
```

For Claude Code, replace the destination with its skills folder; never overwrite an existing install automatically. The installation script copies the portable skill and core to the requested destination and doesn't modify global agent configuration. For [skills.sh](https://skills.sh/) users, the external CLI may also support `npx skills add Guhanavish/mirrormap`; installation in specific agents should be verified rather than assumed.

[**Install & setup guide**](docs/getting-started.md) · [**Agent integration patterns**](docs/integrations/agent-guides.md) · [**MCP contract**](docs/integrations/mcp.md)

## Audit pull requests with GitHub Actions

MirrorMap also ships a [reusable composite action](action.yml) for repositories that want read-only project reports as workflow artifacts. The action requires no third-party service or project dependency installation, and it never runs the checked-out application code.

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
- uses: Guhanavish/mirrormap@main # Pin a reviewed commit SHA for production.
  with:
    mode: quick
```

[Complete PR workflow](examples/github-actions/mirrormap-composite-audit.yml) · [Action inputs, permissions and limitations](docs/integrations/github-action.md)

## The safety contract

- **Intent is independent:** code cannot quietly rewrite requirements.
- **Unverified means unverified:** a file exists ≠ a feature passes tests.
- **Candidate matches never become reviewed evidence automatically.**
- **No edits on audit:** report artifacts are outside the source repository.
- **Human-approved remediation:** generated plans do not authorize themselves; the host controls code changes.
- **Stale evidence doesn't count:** `complete` requires revision-matched verification for acceptance criteria.
- **Honest errors:** missing specs, inaccessible tools and uncertainty are surfaced as limitations.

Read [SECURITY.md](SECURITY.md) and [the evidence model](references/data-model.md).

## Build with us

The project welcomes reproducible reports, language-specific scanners, meaningful CI examples, and integration testing. If you propose a new agent adapter, verify the exact install path and tool capabilities first.

[Report a bug](https://github.com/Guhanavish/mirrormap/issues/new) · [Contribute](CONTRIBUTING.md) · [Engineering standard](docs/IMPLEMENTATION_STANDARD.md) · [Changelog](CHANGELOG.md)

## Share and improve MirrorMap

We'd rather hear about a confusing classification than collect a star that never turns into a real audit. [Try the reproducible fixture](examples/README.md), then [report your first-audit experience](.github/ISSUE_TEMPLATE/real_world_audit.md) or [open an issue](https://github.com/Guhanavish/mirrormap/issues/new).

Maintainers: [launch and community kit](docs/launch/README.md) · [release checklist](docs/launch/release-v0.4.0-beta.md) · [responsible sharing templates](docs/launch/community-posts.md). The source includes a static product landing page, **not a deployed MirrorMap service**.

## Roadmap

- [x] **v0.1 Foundation:** independent maps, structural indexing, evidence-aware diff and reviewed plans.
- [x] **v0.2 Evidence Atlas:** one-command audit, offline dashboard, five scoped modes, doctor, installer, candidate links, baseline comparison, Python API, experimental MCP and CI example.
- [x] **v0.3 Route Atlas:** conservative Next.js and FastAPI route candidates, reusable read-only GitHub composite action, and richer integration guides.
- [x] **v0.4 Interactive Atlas + JUnit import:** functional offline graph/search/zoom/detail UI and opt-in existing JUnit XML ingestion, plus optional GitHub Action evidence inputs.
- [ ] **v0.5 Wider verification:** AST-depth adapters, optional permissioned browser probes, real coverage import and reviewer-friendly link assignment.
- [ ] **v0.6 Connected workflows:** validated cross-agent installers, impact-aware PR audit and CI annotations.
- [ ] **v1.0 Full experience:** hosted documentation/demo, independent verification integrations, host-enforced approval UI and evaluated plugin distribution.

**v0.4 limitations:** The interactive dashboard is a local HTML artifact, **not** a hosted service. JUnit import reads results produced elsewhere, **not** tests it runs. Fully automatic bug detection, browser testing, approved code execution and hosted dashboards remain future work. See [v0.4 release notes](docs/release-notes-v0.4.md).

---

<div align="center">

### **Know what your software promises. Prove what it delivers.**

Made for the open agent ecosystem · MIT licensed · [Creator's website](https://guhanavish.vercel.app/)

**If MirrorMap saves you an audit, consider starring the repo.**

</div>
