# OpenCode role/model matrix

Matrix revision: 2026-10-09 (skill 2.0.0), local quality profile, mixed providers.
Last verified: not yet — no OpenCode review has run on these definitions. Model
IDs assume the `anthropic` and `openai` providers are configured; run one review
and record what ran (see [maintenance](maintenance.md)). Check with
`python3 scripts/check_matrix.py`.

OpenCode is the one runtime that can mix providers in one review. Independent
roles run on a **different model family** than the role they double-check:
Felix (independent) on GPT while Maya (bugs) is on Claude, so their blind spots
differ. Codex-side roles keep the Codex matrix's models and efforts.

| Role | Pinned model ID | Effort | OpenCode agent |
| --- | --- | --- | --- |
| Coordinator | Current session model | Inherit | Current session |
| Finn — guidelines | `openai/gpt-6.1-sol` | high | pr-shepherd-sol |
| Maya — bugs / incremental fix check | `anthropic/claude-opus-5-5` | provider default | pr-shepherd-opus |
| Theo — architecture | `openai/gpt-6.1-sol` | medium | pr-shepherd-sol-medium |
| Nora — types | `openai/gpt-6-luna` | xhigh | pr-shepherd-luna-xhigh |
| Jasper — comments and intent | `openai/gpt-6.1-sol` | high | pr-shepherd-sol |
| Felix — independent reviewer | `openai/gpt-6.1-sol` | high | pr-shepherd-sol |
| Remy — security, routine | `openai/gpt-6.1-sol` | high | pr-shepherd-sol |
| Remy+ — security: auth, permissions, trust boundaries, secrets, infra, cross-service | `openai/gpt-6.1-sol` | xhigh | pr-shepherd-sol-xhigh |
| Ruby — performance | `openai/gpt-6.1-sol` | high | pr-shepherd-sol |
| Oscar — code quality | `openai/gpt-6-luna` | xhigh | pr-shepherd-luna-xhigh |
| Iris — language | `openai/gpt-6-luna` | xhigh | pr-shepherd-luna-xhigh |
| Zoe / Cleo — reflection and debate | `anthropic/claude-opus-5-5` | provider default | pr-shepherd-opus |
| Vera — verification | `openai/gpt-6-luna` | xhigh | pr-shepherd-luna-xhigh |
| Otis / Milo / Luna — fact check, confidence, reachability | `openai/gpt-6.1-sol` | high | pr-shepherd-sol |
| Ada / Eli / Sofia / Hugo / Max — optional companion duties | Coordinator | Inherit | Not counted as review |

"Provider default" means the agent file sets no effort: OpenCode passes
`reasoningEffort` through to OpenAI models, and Anthropic effort is not
configured per agent here until verified. Do not claim an effort that was not set.

## Provider fallback (DeepSeek, GLM)

`install.py --opencode-root …` checks which providers OpenCode can use (API-key
variables, saved logins in `~/.local/share/opencode/auth.json`, provider
sections in `opencode.json(c)`):

| Connected | Reviewer models |
| --- | --- |
| OpenAI (GPT) or Anthropic (Claude) | the table above, linked unchanged |
| neither, but DeepSeek | `deepseek/deepseek-flash` for every role |
| none of those, but GLM (`zhipuai`/`zai`) | `zhipuai/glm-5.3` for every role |
| none of these | the table above, with a warning in the plan that providers are missing |

For DeepSeek or GLM the installer writes marked copies of the agent files with
the model swapped and OpenAI-only `reasoningEffort` removed; `--opencode-profile`
forces a choice. Re-running it after connecting GPT or Claude switches back.
In these profiles every role runs on one model family: say in the plan and PR
that Felix's independent pass is **not** cross-family. Fallback model IDs are
not runtime-verified; check `opencode models` and adjust if your provider names
them differently.

## Dispatch

- Agents live in `agents/opencode/*.md` (Markdown, `mode: subagent`, pinned
  `model`, `edit`/`bash`/`webfetch`/`task` denied). Install them with
  `scripts/install.py --opencode-root ~/.config/opencode/agents`; the remote skill
  index does not install agents. Restart OpenCode after installing.
- Start each role with the `task` tool, `subagent_type` = the agent name, and the
  role's prompt from `scripts/review_packet.py --runtime opencode`.
- Subagent depth is 1 by default, which suits read-only reviewers. Parallel
  background subagents need `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`;
  otherwise roles run one at a time — say so in the plan.
- Track progress with `todowrite`. OpenCode has no scheduler: for the post-PR
  check use one bounded wait (`sleep 300 && gh pr view …` with a bash timeout
  above 300 s) or tell the user the check is still due.
- If a provider or model is not configured, stop that role and report it; never
  substitute silently. Record per role the agent, observed model, tokens and
  duration, as on the other runtimes.
