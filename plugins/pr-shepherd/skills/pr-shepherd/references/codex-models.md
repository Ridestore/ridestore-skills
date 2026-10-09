# Codex role/model matrix

Use native Codex subagents. Do not run Claude models or Claude CLI as a hidden
fallback. Matrix revision: 2026-10-09 (skill 2.0.0), local quality profile: the same
models per role as a production server-side reviewer's normal policy, one
reasoning-effort step higher (medium → high; xhigh stays xhigh). `gpt-6-astra`
is used only for security review, at medium effort. `gpt-6-luna` never runs
below high effort.
These defaults use versioned IDs exposed by the Codex host;
check the current tool's available models and supported efforts before use.
An explicit user selection takes precedence. GPT-6.1 Sol/high native review
calls were exercised on 2026-10-07; the matrix is a policy, not evidence that
every model/effort combination ran. Recheck the live tool catalog each session.
Do not change the coordinator's model or reasoning setting automatically.

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

The coordinator remains the current task agent; do not create a new
user-owned task merely to select a coordinator model. If a listed default is unavailable, report it before dispatch and record an
explicit substitute of equal/higher review capability from the live catalog.
Do not silently downgrade to Luna or use the parent as its own reviewer. An
exact model required by the user needs their agreement before substitution. If no model/agent tool
can complete the required independent review, leave the review incomplete;
do not attest a passing local review.

With this host's `collaboration.spawn_agent`, a full-history fork inherits the
parent model and cannot accept model overrides. For a matrix assignment, set
`fork_turns: "none"` and supply the complete bounded review packet in the
message, plus the selected `model` and `reasoning_effort`. Read the live schema
on other Codex versions rather than assuming the same tool names.

Example assignment on this host:

```json
{
  "task_name": "local_review_bugs",
  "fork_turns": "none",
  "model": "gpt-6.1-sol",
  "reasoning_effort": "high",
  "message": "Read-only Maya review. Repository/worktree: <absolute path>. Base: <sha>. Head: <sha>. Read <skill references>, applicable repository rules, full diff and relevant callers. <user acceptance criteria>. Report the structured review result. Do not edit, commit, push, contact GitHub, or start other agents. Other agents share this checkout; preserve their work."
}
```

The invoking skill authorizes these bounded model-specific review agents.
Respect the host concurrency limit; with four slots including the coordinator,
run at most three reviewers concurrently and queue the rest. Wait for every
required role. Inspect actual tool results; do not report the planned model as
an observed execution when the tool did not confirm it.

Model configuration changes are maintained through [maintenance](maintenance.md).
This local matrix is intentionally at least as capable as the normal policy of
downstream review automation and above any reduced-cost mode; server role/model
caps do not apply here.

Discovery reference: [Codex skill loader](https://github.com/openai/codex/blob/main/codex-rs/ext/skills/src/loader/host.rs).
The live Codex tool schema is authoritative for model overrides and agent tools.
