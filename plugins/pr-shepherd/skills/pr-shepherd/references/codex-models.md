# Codex role/model matrix

Matrix revision: 2026-10-09 (skill 2.0.0), local quality profile: the same
models per role as a production server-side reviewer's normal policy, one
reasoning-effort step higher (medium → high; xhigh stays xhigh). `gpt-6-astra`
only for security review, at medium. `gpt-6-luna` never runs below high.
Last verified: 2026-10-07 — GPT-6.1 Sol/high native review calls ran on Codex;
the other model/effort combinations are policy, not observed runs. Check with
`python3 scripts/check_matrix.py`, and recheck the live tool catalog each session.

Use native Codex subagents; no hidden Claude fallback. An explicit user selection
takes precedence. Do not change the coordinator's model or reasoning setting.

| Role | Default model | Effort |
| --- | --- | --- |
| Coordinator | Current parent Codex model; recommended `gpt-6.1-sol` for a newly user-configured session | Inherit parent |
| Finn — guidelines | `gpt-6.1-sol` | high |
| Maya — bugs / incremental fix check | `gpt-6.1-sol` | high |
| Theo — architecture | `gpt-6.1-sol` | high |
| Nora — types | `gpt-6-luna` | xhigh |
| Jasper — comments and intent | `gpt-6.1-sol` | high |
| Felix — independent reviewer | `gpt-6.1-sol` | high |
| Remy — security | `gpt-6-astra` | medium |
| Ruby — performance | `gpt-6.1-sol` | high |
| Oscar — code quality | `gpt-6-luna` | xhigh |
| Iris — language | `gpt-6-luna` | xhigh |
| Zoe / Cleo — reflection and debate | `gpt-6.1-sol` | high |
| Vera — verification | `gpt-6-luna` | xhigh |
| Otis / Milo / Luna — fact check, confidence, reachability | `gpt-6.1-sol` | high |
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
  "reasoning_effort": "high",
  "message": "<contents of prompts/maya.md from the review packet>"
}
```

- Respect the host's concurrency limit (with four slots including the
  coordinator, at most three reviewers at once; queue the rest). Wait for every
  required role and record what actually ran, with tokens and duration, not the
  planned model.

This matrix is at least as capable as downstream review automation's normal
policy; server caps do not apply. Changes: [maintenance](maintenance.md).
Discovery: [Codex skill loader](https://github.com/openai/codex/blob/main/codex-rs/ext/skills/src/loader/host.rs).
