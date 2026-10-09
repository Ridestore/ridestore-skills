# Claude Code role/model matrix

Matrix revision: 2026-10-09 (skill 2.0.0), local quality profile. Use native
Claude Agent/subagents; no hidden Codex/OpenAI fallback. Explicit user model
choices take precedence. Keep the current coordinator and its reasoning setting;
do not start another user-owned chat to select a model.

| Role | Pinned model ID | Effort | Native reviewer definition |
| --- | --- | --- | --- |
| Coordinator | Inherit current parent; recommend `claude-opus-5-5` for a user-selected new session | Inherit parent | Existing parent |
| Finn — guidelines | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Maya — bugs / incremental fix check | `claude-opus-5-5` | high | opus-reviewer |
| Theo — architecture | `claude-opus-5-5` | high | opus-reviewer |
| Nora — types | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Jasper — comments and intent | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Felix — independent reviewer | `claude-opus-5-5` | high | opus-reviewer |
| Remy — security | `claude-opus-5-5` | high | opus-reviewer |
| Ruby — performance | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Oscar — code quality | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Iris — language | `claude-sonnet-5-5` | high | sonnet-reviewer |
| Zoe / Cleo — reflection and debate | `claude-opus-5-5` | high | opus-reviewer |
| Vera / Otis / Milo / Luna — evidence and reachability | `claude-opus-5-5` | high | opus-reviewer |
| Ada / Eli / Sofia / Hugo / Max — optional companion duties | Coordinator, or `claude-sonnet-5-5` if separately delegated | Coordinator's own, or high when delegated | Not counted as review |

The registered definitions live in `agents/*-reviewer.md` in this
package and are the source of truth for Claude model pins. Install them using
[maintenance](maintenance.md). They are two model templates, not two shared
review conversations: start a fresh call per planned role with the role name and
complete frozen review packet. Keep Felix separate from Maya and do not show
Felix earlier findings before its first result.

Effort is pinned in each definition's frontmatter (`effort: high`), next to
`model`; plugin-shipped agents honor both fields. The Agent tool has no per-call
effort, so a role that needs a different effort needs its own definition.
`/tasks` and the status line show the configured effort of a running reviewer.

Claude Code custom-agent definitions support full IDs. Some Agent tool schemas
accept only aliases in the per-call `model` field. For those hosts, select the
registered `subagent_type` and **omit** per-call `model`, which would override
the pinned definition. Do not invent a full-ID value for an alias-only enum.
Session launchers can register the same definitions with `--agents`; interactive
sessions load installed agent files. After an installation/update, reload agent
definitions through the supported UI or start a new session before dispatch.

When the package is installed as the `pr-shepherd` Claude Code plugin, the
definitions register with the plugin scope: `pr-shepherd:opus-reviewer`
and `pr-shepherd:sonnet-reviewer`. Use the exact name the Agent tool
lists; a scoped and an unscoped copy of the same definition are equivalent.

Read the live Agent/Task schema; the native name varies by version. Use native
TaskCreate/TaskUpdate for progress where available. Do not add an unsupported
Agent `effort` field. Review tools default to Read/Grep/Glob; if a finding needs
execution or current documentation, the coordinator gathers the bounded evidence
with permitted tools and the independent evidence reviewer verifies it. State
unavailable evidence explicitly rather than making the reviewer run forbidden
commands. The skill stays in the current coordinator context (no `context: fork`).

Record the selected full ID, native call ID and observed response model for each
role. In a CLI audit, child events forwarded with `--forward-subagent-text` expose
`message.model` and `parent_tool_use_id`; the interactive `/tasks` view can expose
the resolved model. Validate process/tool success and `is_error`, plus actual
child results. Init metadata, self-reported model names and `subtype: success`
alone are insufficient. If a selector resolves differently, expose the mismatch;
do not claim the configured version ran. Missing model identity remains unknown.

When a pinned model or registered definition is unavailable, stop that review
role, explain the exact failure and repair discovery/authentication or obtain the
user's agreement to a named substitute. Do not silently use a floating alias,
the parent as its own reviewer, another provider or Haiku. Missing independent
calls leave the review incomplete; never attest a passing local review.

On 2026-10-07, Claude Code 2.1.285 discovered the installed definitions and
executed native Opus 5.5 and Sonnet 5.5 review calls with completed results,
visible task transitions and a clean control. This establishes the tested
account's mechanism, not universal access or a complete PR review. Check the
installed runtime each time.

Primary sources: [native subagents](https://code.claude.com/docs/en/sub-agents),
[skills](https://code.claude.com/docs/en/skills),
[model IDs and versions](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions).
Runtime evidence takes precedence over a moving convenience alias.
