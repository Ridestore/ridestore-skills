# Claude Code role/model matrix

Matrix revision: 2026-10-09 (skill 2.4.0), speed profile.
Last verified: 2026-10-09 — on the local review of skill 2.4.0 (Claude Code
2.1.295), `opus-reviewer-medium` ran Maya (132k tokens, 3.9 min; recheck 74k,
1.8 min) and Theo (184k, 4.7 min), and `sonnet-reviewer` (effort high) ran the
merged Finn+Jasper call (146k, 4.1 min; recheck 109k, 2.2 min), all returning
complete results (observed response model not captured). `sonnet-reviewer-medium` is new in 2.4.0 and not yet runtime-verified.
Check with `python3 scripts/check_matrix.py` (definitions, pins, verification age).

Use native Claude subagents; no hidden Codex/OpenAI fallback. Explicit user model
choices take precedence. Keep the current coordinator and its reasoning setting.

| Role | Pinned model ID | Effort | Native reviewer definition |
| --- | --- | --- | --- |
| Coordinator | Inherit current parent; recommend `claude-opus-5-5` for a new session | Inherit parent | Existing parent |
| Finn — guidelines | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Maya — bugs / incremental fix check | `claude-opus-5-5` | medium | opus-reviewer-medium |
| Theo — architecture | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Nora — types | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Jasper — comments and intent | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Felix — independent reviewer | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Remy — security, routine | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Remy+ — security: auth, permissions, trust boundaries, secrets, infra, cross-service | `claude-opus-5-5` | medium | opus-reviewer-medium |
| Ruby — performance | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Oscar — code quality | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Iris — language | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Zoe / Cleo — reflection and debate | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Vera — verification | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Otis / Milo / Luna — fact check, confidence, reachability | `claude-sonnet-5-5` | medium | sonnet-reviewer-medium |
| Ada / Eli / Sofia / Hugo / Max — optional companion duties | Coordinator, or `claude-sonnet-5-5` if delegated | Coordinator's own, or medium when delegated | Not counted as review |

Since 2.4.0 Opus never runs above medium and is used only for bugs (Maya) and
sensitive security (Remy+); every other role runs Sonnet, at high for types,
code quality and language and at medium for the rest. Felix on Sonnet also gives
the independent pass a different model than Maya's, so their blind spots differ.
Everything runs one effort step lower than before: on a real Deep review
(2026-10-09) Opus at high took about 6.5 minutes and Sonnet at xhigh about 8.
Maya has run at medium since 2.1.0 (Theo did too until it moved to Sonnet in
2.4.0). Whether medium finds as much is not measured yet; the xhigh and
Opus-high definitions were removed.

## Dispatch

- The three definitions in `agents/*-reviewer*.md` are the source of truth for
  model and effort pins. They are templates, not shared conversations: start a
  fresh call per planned role with the role name and complete review packet.
  Keep Felix separate from Maya and show him no earlier findings.
- Effort lives in each definition's frontmatter; the Agent tool has no per-call
  effort, so a different effort needs its own definition. Plugin-shipped agents
  honor `model` and `effort`. `/tasks` and the status line show both.
- Select the registered `subagent_type` and **omit** the per-call `model`, which
  would override the pin. As a plugin the names are scoped
  (`pr-shepherd:opus-reviewer-medium`, …); use the exact name the Agent tool lists.
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
