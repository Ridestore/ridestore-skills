# Claude Code role/model matrix

Matrix revision: 2026-10-09 (skill 2.0.0), local quality profile.
Last verified: 2026-10-09 — Claude Code 2.1.295 ran `opus-reviewer` and
`sonnet-reviewer` (Opus 5.5 / Sonnet 5.5, effort high) as native read-only
reviewers on a real PR review; `sonnet-reviewer-xhigh` ran Nora on a real
review the same day and returned a complete result (observed response model not
captured). `opus-reviewer-xhigh` and `opus-reviewer-medium` are not yet runtime-verified.
Check with `python3 scripts/check_matrix.py` (definitions, pins, verification age).

Use native Claude subagents; no hidden Codex/OpenAI fallback. Explicit user model
choices take precedence. Keep the current coordinator and its reasoning setting.

| Role | Pinned model ID | Effort | Native reviewer definition |
| --- | --- | --- | --- |
| Coordinator | Inherit current parent; recommend `claude-opus-5-5` for a new session | Inherit parent | Existing parent |
| Finn — guidelines | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Maya — bugs / incremental fix check | `claude-opus-5-5` | medium | opus-reviewer-medium |
| Theo — architecture | `claude-opus-5-5` | medium | opus-reviewer-medium |
| Nora — types | `claude-sonnet-5-5` | xhigh | sonnet-reviewer-xhigh |
| Jasper — comments and intent | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Felix — independent reviewer | `claude-opus-5-5` | high | opus-reviewer |
| Remy — security, routine | `claude-opus-5-5` | high | opus-reviewer |
| Remy+ — security: auth, permissions, trust boundaries, secrets, infra, cross-service | `claude-opus-5-5` | xhigh | opus-reviewer-xhigh |
| Ruby — performance | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Oscar — code quality | `claude-sonnet-5-5` | xhigh | sonnet-reviewer-xhigh |
| Iris — language | `claude-sonnet-5-5` | xhigh | sonnet-reviewer-xhigh |
| Zoe / Cleo — reflection and debate | `claude-opus-5-5` | high | opus-reviewer |
| Vera — verification | `claude-opus-5-5` | xhigh | opus-reviewer-xhigh |
| Otis / Milo / Luna — fact check, confidence, reachability | `claude-opus-5-5` | high | opus-reviewer |
| Ada / Eli / Sofia / Hugo / Max — optional companion duties | Coordinator, or `claude-sonnet-5-5` if delegated | Coordinator's own, or high when delegated | Not counted as review |

The xhigh rows mirror the Codex matrix, where the same roles run at xhigh. A
model without xhigh runs it as high. Maya and Theo run Opus at medium (since
2.1.0): measured on real reviews, they were the slowest roles at high (about 6
minutes on a Deep review). Whether medium finds as much is not measured yet.

## Dispatch

- The five definitions in `agents/*-reviewer*.md` are the source of truth for
  model and effort pins. They are templates, not shared conversations: start a
  fresh call per planned role with the role name and complete review packet.
  Keep Felix separate from Maya and show him no earlier findings.
- Effort lives in each definition's frontmatter; the Agent tool has no per-call
  effort, so a different effort needs its own definition. Plugin-shipped agents
  honor `model` and `effort`. `/tasks` and the status line show both.
- Select the registered `subagent_type` and **omit** the per-call `model`, which
  would override the pin. As a plugin the names are scoped
  (`pr-shepherd:opus-reviewer`, …); use the exact name the Agent tool lists.
- After installing or updating definitions, reload agents or start a new session.
- Reviewers have Read/Grep/Glob only. If a finding needs execution or current
  docs, the coordinator gathers bounded evidence and the evidence agent verifies
  it. The skill stays in the coordinator's context (no `context: fork`).

## Evidence of what ran

Record per role: definition, native call ID, observed response model, tokens and
duration (the completion notification reports `subagent_tokens` and
`duration_ms`). In a CLI audit, `--forward-subagent-text` exposes `message.model`
and `parent_tool_use_id`. Self-reported model names, init metadata or
`subtype: success` alone are not evidence; a mismatch is reported, never hidden.

If a pinned model or definition is unavailable, stop that role, report the
failure and repair it or get the user's agreement to a named substitute. Never
silently use a floating alias, the parent as its own reviewer, another provider
or Haiku. Missing independent calls leave the review incomplete.

Sources: [subagents](https://code.claude.com/docs/en/sub-agents),
[model IDs](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions).
