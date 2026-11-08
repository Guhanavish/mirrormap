# MirrorMap v0.4.0 beta — Interactive Evidence Atlas

This release concentrates on two previously missing user-facing capabilities while preserving the read-only, evidence-first audit contract.

## Shipped

- **Offline interactive dashboard:** real graph layout of intent, implementation, and verification lanes, search, classification filters, zoom, keyboard-selectable nodes and evidence inspector.
- **JUnit XML ingestion:** parse existing test reports without invoking them, collect SHA-256 hashes, record pass/fail/skip as raw observations, and expose them as unlinked candidates by default.
- **Promote only reviewed tests:** mapping requires `reviewed: true`, exact Git HEAD, a known requirement, its exact acceptance criterion and a unique testcase key. This still does **not** attest when that test ran or the sufficiency of its assertions.
- **CI integration:** the reusable GitHub Action can import a bounded report within the checked-out workspace; it does not run project tests or use privileged GitHub permissions.
- **Examples and tests:** JUnit sample, mapping template, browser-tested offline UI, XML security and integration tests.

## Not shipped

Automatic project test execution, hosted UI, browser testing runners, code-changing automation, cross-agent installer certification, complete framework parsers, and GitHub Release creation are separate future work. The old CLI interfaces continue to work.

## Security

No application code execution, no repository writes, no remote frontend scripts or telemetry. XML DTDs/entities are rejected, inputs have bounded size/count and unexpected mappings fail closed. Sensitive information may appear in test names or filenames; review public CI reports before sharing.
