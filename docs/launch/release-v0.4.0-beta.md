# Prepared release notes — MirrorMap v0.4.0 beta

**This file is release copy, not a published GitHub Release.** Intended tag: v0.4.0-beta. Check the exact commit to be tagged.

MirrorMap is a portable Agent Skill and Python CLI for evidence-backed project audits. It compares approved requirements, structural implementation evidence and observed tests, then produces an offline interactive visualization and a review-only improvement plan.

### Shipped capabilities

- Interactive offline Evidence Atlas: search, filters, zoom and linked evidence.
- Import of existing JUnit XML test reports, with independently reviewed mappings required before promoting results to acceptance-criterion evidence.
- Quick, deep, PR, drift and visual audit modes, each bounded by available inputs.
- Candidate route inventory for selected Next.js and FastAPI patterns.
- Reusable read-only GitHub Action, Python CLI, portable SKILL.md and structured JSON reports.

### Try the bundled example

    git clone https://github.com/Guhanavish/mirrormap.git
    cd mirrormap
    python -m projectmirror audit examples/demo-app --spec examples/demo-app/requirements.md --approved-spec --mode deep

The approved-spec flag refers to the **prepared fixture**. For real projects it must reflect actual user approval.

### What this beta does not do

No automatic application test execution, hosted dashboard, deployment, code editing, exhaustive bug detection or independently verified installation across every agent platform. See SECURITY.md for details.

### Maintainer release checklist

- [ ] Run GitHub CI for Python 3.10, 3.11, 3.12 and 3.13 on the exact target commit.
- [ ] Verify source archive and build wheel from that same commit.
- [ ] Create tag v0.4.0-beta against the intended commit.
- [ ] Publish a **prerelease**, attach verified assets and hashes.
- [ ] Confirm the public Release URL before publishing badges or promotional announcements.
