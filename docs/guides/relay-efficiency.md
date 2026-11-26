# Relay Token Efficiency Engine (development preview)

Relay performs deterministic local processing. Its Python/SQLite/Git operations do not invoke a language model or send project information to a provider. The host agent may still consume tokens for hook instructions, its own summaries, tool calls/results, and recovered context. Token usage depends on host caching, tokenizer, and billing. No actual provider token savings have been measured.

## Recording modes

| Mode | Reminder policy | Automatic tool tracking |
| --- | --- | --- |
| eco (default) | Short initial hint if milestones are missing; subsequent eligible hint only after at least 40 recorded completed-tool/file-edit events and 600 seconds since the last note/save/reminder | Yes |
| balanced | Same policy with 12 events and 180 seconds | Yes |
| detailed | Same policy with 5 events and 60 seconds | Yes |
| manual | No automatic milestone hints; only SessionStart registration, then explicit save/checkpoint | No |

Thresholds are eligibility conditions, not timers. Reminders are emitted only at supported prompt/start hook boundaries; Cursor only at SessionStart. An explicit note or save resets the cadence. These are not guarantees that all hooks are delivered. The local journal counts reminders prepared for output, not tokens billed or even confirmed delivered by the host. Manual mode cannot detect operations started between checkpoints; Relay refuses automatic readiness/adoption when it has recorded a manual coverage gap. Use the recovered context for manual inspection.

Review installation changes before applying:

```sh
python -m projectmirror relay install-hooks --agent claude --project /absolute/project --mode eco
python -m projectmirror relay install-hooks --agent claude --project /absolute/project --mode eco --apply
```

Replace the mode or agent as desired. Reinstallation removes recognized older MirrorMap command variants for the same project while preserving unrelated hooks. Excerpt collection remains a separate explicit `--capture-context` opt-in (unavailable in manual mode). No raw transcripts or tool payloads are read. Metadata-only remains the privacy default. Old sessions are readable without rewriting their event journals; newly written delta checkpoints require the upgraded CLI to recover.

## Efficient handoff

```sh
mirrormap relay sessions
mirrormap relay save --session ID --stage debugging --next "Verify independent seek"
mirrormap relay recover --session ID --budget compact
mirrormap relay recover --session ID --max-tokens 1500 --query "audio output seek"
```

Prefer `recover` over the legacy `resume` envelope for minimum duplication. Compact, standard, and detailed have 8,000/32,000/64,000 UTF-8 byte targets respectively. `--max-tokens` additionally caps the target at four UTF-8 bytes per estimated token. This is a heuristic, not a tokenizer or hard provider token limit. The CLI emits compact JSON; transport wrappers, other prompt content, and the model's responses are excluded. Mandatory safety context, blockers, corrections, task cursor, and verification are retained; if they alone exceed the target, the response explicitly reports overflow. Do not silently drop warnings to meet a target. Optional exact duplicates are removed retaining latest provenance. Keyword matching ranks optional context; it is lexical, not semantic. Explicit query filters optional items only; without one, other items may fit after relevant items. Contradictory requirements are not automatically resolved.

Fetch more only when needed. Use the same checkpoint ID and query throughout a page sequence:

```sh
mirrormap relay context --session ID --checkpoint NUMBER --query "seek" --limit 5
mirrormap relay context --session ID --checkpoint NUMBER --query "seek" --offset NEXT_OFFSET --limit 5
```

Without a query, retrieve recent optional entries. A null next offset ends the page sequence; if budget_exceeded is true and items are empty, increase the budget before retrying. The catalog also exposes older recorded corrections, blockers, and audit links. This does not grant authority, and the historical checkpoint itself is read-only. Existing history and recovery checks remain intact.

MCP clients can use `mirrormap_relay_brief` and `mirrormap_relay_context`, constrained to the configured allowlisted workspace. The existing `mirrormap_relay_resume` tool remains for compatibility.

## Delta journal and metrics

New events retain task-state changes at field granularity relative to the preceding checkpoint, with a full anchor at least every 16 events. Empty changes are represented by an empty delta. The journal still records supported tool boundaries, verifies the event chain and delta digests, and reconstructs historical state. Changed lists are stored as whole fields; this is not a binary diff or full transcript compression. Consecutive identical captured excerpts are suppressed, and exact duplicate task-note lists are deduplicated. Old event records are not rewritten. Local journal storage savings are distinct from AI token savings.

```sh
mirrormap relay usage --session ID
```

Usage reports local event counts, checkpoint delta counts, duplicate excerpt suppression, reminder bytes and estimated reminder tokens, serialized journal detail sizes versus full reconstructed state, and compact/detailed payload estimates. These estimates use ceil(UTF-8 bytes / 4); they are not provider billing, actual context window consumption, or measured counterfactual savings. Actual tokens saved remains unknown until independent host measurements are supplied. For a fair benchmark, run comparable tasks with and without Relay, same model/version, tool settings, and starting repository; record provider-reported uncached/cached input and output tokens, final task quality, and number of repeated investigations. Synthetic tests validate mechanics, not real-host performance.
