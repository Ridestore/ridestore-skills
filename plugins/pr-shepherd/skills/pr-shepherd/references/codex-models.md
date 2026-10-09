# Codex role/model matrix

Matrix revision: 2026-10-09 (skill 2.4.2), cost profile: GPT-6.1 Sol only where
it matters most, bugs (Maya, medium) and sensitive security (Remy+, high, one step
above routine Remy; see [roles](roles.md)). Every other role runs GPT-6 Luna, at
xhigh for the general roles and at high (it never runs below high) for types, code
quality, language and verification. Sol is the expensive model. Felix on Luna also
gives the independent pass a different model than Maya's.
This skill does not use `gpt-6-astra`.
Last verified: 2026-10-07 — GPT-6.1 Sol/high native review calls ran on Codex;
the other model/effort combinations are policy, not observed runs. Check with
`python3 scripts/check_matrix.py`, and recheck the live tool catalog each session.

Use native Codex subagents; no hidden Claude fallback. An explicit user selection
takes precedence. Do not change the coordinator's model or reasoning setting.

| Role | Default model | Effort |
| --- | --- | --- |
| Coordinator | Current parent Codex model; recommended `gpt-6.1-sol` for a newly user-configured session | Inherit parent |
| Finn — guidelines | `gpt-6-luna` | xhigh |
| Maya — bugs / incremental fix check | `gpt-6.1-sol` | medium |
| Theo — architecture | `gpt-6-luna` | xhigh |
| Nora — types | `gpt-6-luna` | high |
| Jasper — comments and intent | `gpt-6-luna` | xhigh |
| Felix — independent reviewer | `gpt-6-luna` | xhigh |
| Remy — security, routine | `gpt-6-luna` | xhigh |
| Remy+ — security: auth, permissions, trust boundaries, secrets, infra, cross-service | `gpt-6.1-sol` | high |
| Ruby — performance | `gpt-6-luna` | xhigh |
| Oscar — code quality | `gpt-6-luna` | high |
| Iris — language | `gpt-6-luna` | high |
| Zoe / Cleo — reflection and debate | `gpt-6-luna` | xhigh |
| Vera — verification | `gpt-6-luna` | high |
| Otis / Milo / Luna — fact check, confidence, reachability | `gpt-6-luna` | xhigh |
| Ada / Eli / Sofia / Hugo / Max — optional companion duties | Coordinator, or `gpt-6-luna` if separately delegated | high |

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

```json
{
  "task_name": "local_review_bugs",
  "fork_turns": "none",
  "model": "gpt-6.1-sol",
  "reasoning_effort": "medium",
  "message": "<contents of prompts/maya.md from the review packet>"
}
```

- Respect the host's concurrency limit (with four slots including the
  coordinator, at most three reviewers at once; queue the rest). Wait for every
  required role and record what actually ran, with tokens and duration, not the
  planned model.

Server caps of downstream review automation do not apply to this matrix. Changes: [maintenance](maintenance.md).
Discovery: [Codex skill loader](https://github.com/openai/codex/blob/main/codex-rs/ext/skills/src/loader/host.rs).
