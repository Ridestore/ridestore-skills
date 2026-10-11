# Codex role/model matrix

Matrix revision: 2026-10-10 (skill 2.5.0), cost profile: GPT-6.1 Sol only where
it matters most, bugs (Pandora, medium) and sensitive security (Athena, high, one step
above routine Artemis; see [roles](roles.md)). Every other role runs GPT-6 Luna, at
xhigh for the general roles and at high (it never runs below high) for types, code
quality, language and verification. Sol is the expensive model. Odysseus on Luna also
gives the independent pass a different model than Pandora's.
This skill does not use `gpt-6-astra`.
Last verified: 2026-10-07 — GPT-6.1 Sol/high native review calls ran on Codex;
the other model/effort combinations are policy, not observed runs. Check with
`python3 scripts/check_matrix.py`, and recheck the live tool catalog each session.

Use native Codex subagents; no hidden Claude fallback. An explicit user selection
takes precedence. Do not change the coordinator's model or reasoning setting.

| Role | Default model | Effort |
| --- | --- | --- |
| Coordinator | Current parent Codex model; recommended `gpt-6.1-sol` for a newly user-configured session | Inherit parent |
| Themis — guidelines | `gpt-6-luna` | xhigh |
| Pandora — bugs / incremental fix check | `gpt-6.1-sol` | medium |
| Daedalus — architecture | `gpt-6-luna` | xhigh |
| Proteus — types | `gpt-6-luna` | high |
| Mnemosyne — comments and intent | `gpt-6-luna` | xhigh |
| Odysseus — independent reviewer | `gpt-6-luna` | xhigh |
| Artemis — security, routine | `gpt-6-luna` | xhigh |
| Athena — security: auth, permissions, trust boundaries, secrets, infra, cross-service | `gpt-6.1-sol` | high |
| Icarus — performance | `gpt-6-luna` | xhigh |
| Hephaestus — code quality | `gpt-6-luna` | high |
| Palamedes — language | `gpt-6-luna` | high |
| Psyche / Harmonia — reflection and debate | `gpt-6-luna` | xhigh |
| Theseus — verification | `gpt-6-luna` | high |
| Aletheia / Metis / Ariadne — fact check, confidence, reachability | `gpt-6-luna` | xhigh |
| Calliope / Prometheus / Cadmus / Cassandra / Peitho — optional companion duties | Coordinator, or `gpt-6-luna` if separately delegated | high |

## Dispatch

- If a listed model is unavailable, report it before dispatch and record an
  explicit substitute of equal or higher capability from the live catalog. Never
  silently downgrade or use the parent as its own reviewer; a model the user
  required needs their agreement to substitute. Without any agent tool the
  review is incomplete.
- With `collaboration.spawn_agent`, a full-history fork inherits the parent model
  and ignores overrides: set `fork_turns: "none"` and pass the complete packet
  (from `scripts/review_packet.py`) plus `model` and `reasoning_effort`. Read the
  live schema on other Codex versions.

Codex's native `collaboration.spawn_agent` shows `task_name` in the child list.
A `label` in the manifest, prompt or progress message does not name that child.
For each call, copy the role's `codex_spawn` fields from `manifest.json` and add
`message` containing its generated prompt. The human `label` uses
`Name (Role · model effort)`, for example `Daedalus (Architecture review · Luna xhigh)`.
Use only the short model family, such as `Luna` or `Sol`, in labels; keep the exact
model selector in the spawn's `model` field. The native fallback puts the persona
first, followed by the role, short model and effort. It uses only lowercase
letters, digits and underscores accepted by this tool; the UI controls spacing
and capitalization. This native schema cannot preserve the human label's
parentheses or middle dot. Use the human label in progress reports and do not
claim the fallback has that exact visual formatting. Do not send an invented
`label` or `description` argument.

```json
{
  "task_name": "pandora_bugs_review_sol_medium",
  "fork_turns": "none",
  "model": "gpt-6.1-sol",
  "reasoning_effort": "medium",
  "message": "<contents of prompts/pandora.md from the review packet>"
}
```

For repeat calls, preserve that descriptive name and append `_r2`, `_r3`, etc.
`--previous-head` packets also put `recheck` in the generated name. A substantial
fix still needs the full-diff review required by `local-review.md`; its new call
gets a round suffix even though the packet has no `--previous-head`.
For merged roles and evidence calls, keep the lead persona first and use a
concise combined purpose, for example `themis_guidelines_comments_luna_xhigh`
or `aletheia_verify_findings_luna_xhigh`. List every covered role in the prompt
and review record; do not append a long list of personas to the native name. Never use just
`pandora`, `docs_recheck` or `evidence`. A follow-up on an existing child keeps
its existing name; start a correctly named child if its purpose/model changes.

If an authorized override or live-catalog substitution changes model or effort,
update the spawn fields, native task name **and human label** from the same
dispatched settings before calling. Use that updated label in progress reports
and review records. These describe the
requested dispatch settings, not independently observed execution telemetry;
record any unavailable telemetry as unknown. Other Codex tool versions may
expose a display-name field: inspect their actual schema, use the human `label`
there, and never assume the native API above has that field.

- Respect the host's concurrency limit (with four slots including the
  coordinator, at most three reviewers at once; queue the rest). Wait for every
  required role and record what actually ran, with tokens and duration, not the
  planned model.

Server caps of downstream review automation do not apply to this matrix. Changes: [maintenance](maintenance.md).
Discovery: [Codex skill loader](https://github.com/openai/codex/blob/main/codex-rs/ext/skills/src/loader/host.rs).
