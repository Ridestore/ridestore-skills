# DeepSeek Harness (dsh) role/model matrix

Matrix revision: 2026-10-09 (skill 2.4.0), DeepSeek models only.
Last verified: not yet — no dsh review has run on these definitions. Written
against dsh 0.2.0-rc.2 (npm `latest`) and the 0.2.1 alpha source; record what
ran (see [maintenance](maintenance.md)). Check with `python3 scripts/check_matrix.py`.

dsh runs only DeepSeek models here: `deepseek-flash` (DeepSeek-V4.1-Flash) for
every role. DeepSeek's reasoning efforts are `off`, `low`, `high` and `max` (no
`medium` or `xhigh`), so roles at medium or high on the other runtimes run at
`high`, and roles at xhigh run at `max`. Every role is on one model family: say
in the plan and PR that Felix's independent pass is **not** cross-family.

| Role | Pinned model ID | Effort | dsh tool |
| --- | --- | --- | --- |
| Coordinator | Current session model | Inherit | Current session |
| Finn — guidelines | `deepseek-flash` | high | pr_shepherd_flash |
| Maya — bugs / incremental fix check | `deepseek-flash` | high | pr_shepherd_flash |
| Theo — architecture | `deepseek-flash` | high | pr_shepherd_flash |
| Nora — types | `deepseek-flash` | max | pr_shepherd_flash_max |
| Jasper — comments and intent | `deepseek-flash` | high | pr_shepherd_flash |
| Felix — independent reviewer | `deepseek-flash` | high | pr_shepherd_flash |
| Remy — security, routine | `deepseek-flash` | high | pr_shepherd_flash |
| Remy+ — security: auth, permissions, trust boundaries, secrets, infra, cross-service | `deepseek-flash` | max | pr_shepherd_flash_max |
| Ruby — performance | `deepseek-flash` | high | pr_shepherd_flash |
| Oscar — code quality | `deepseek-flash` | max | pr_shepherd_flash_max |
| Iris — language | `deepseek-flash` | max | pr_shepherd_flash_max |
| Zoe / Cleo — reflection and debate | `deepseek-flash` | high | pr_shepherd_flash |
| Vera — verification | `deepseek-flash` | max | pr_shepherd_flash_max |
| Otis / Milo / Luna — fact check, confidence, reachability | `deepseek-flash` | high | pr_shepherd_flash |
| Ada / Eli / Sofia / Hugo / Max — optional companion duties | Coordinator | Inherit | Not counted as review |

## Install

dsh has no skill marketplace for this repository; install from a clone:

```sh
python3 scripts/install.py --install --dsh-home ~/.dsh
```

- Links the skill to `<dsh-home>/skills/pr-shepherd`. dsh also finds skills in
  `~/.agents/skills`, so the Codex link works too; duplicates resolve by rank.
- Appends the rows of `agents/dsh/cordis.patch.yml` to `<dsh-home>/cordis.patch.yml`
  (the home patch, applied to every profile) between
  `# >>> pr-shepherd (managed by install.py) >>>` and `# <<< pr-shepherd <<<`.
  Re-running updates only that block; content outside it (line endings
  included) is kept, and the file is replaced atomically. The installer refuses a
  file that is not a YAML block list at column 0, or that already inserts these
  rows or tool names outside the block. Overriding a managed row by id after the
  block (`- id: pr-shepherd-flash` with `disabled: true`, say) is allowed.
- The home patch applies to every profile, so both tools appear in every dsh
  session, not only pr-shepherd runs.
- The installer does not read `$DSH_HOME`; if you set it, pass
  `--dsh-home "$DSH_HOME"`. `dsh web` hot-reloads the home patch; restart
  `headless`, `acp` and `sdk` sessions. Preview the result without booting:
  `dsh --profile headless --dump-config`.
- DeepSeek credentials: the `deepseek-official` provider reads `DEEPSEEK_API_KEY`
  (environment, `<dsh-home>/.credentials.yaml` or `.env`). dsh requires Node
  22.19+ or 24+ (its `engines` field).

## Dispatch

- Start each role with the tool from the table (`pr_shepherd_flash` or
  `pr_shepherd_flash_max`); `description` = the role name, `prompt` = the role's
  prompt from `scripts/review_packet.py --runtime dsh`, `cwd` = the task tree.
  The tools pin provider, model and effort; do not use the generic `subagent`
  tool or its model selection for reviewers.
- **Before dispatch, check your own tool list.** If `pr_shepherd_flash` or
  `pr_shepherd_flash_max` is missing, the install step did not run: do not
  dispatch, mark the review incomplete and tell the user to run
  `install.py --install --dsh-home ~/.dsh` and restart dsh. If `run_code` is
  present, the session uses PTC tool presentation (the web `ptc` preset or
  `tools.mode: ptc`), where reviewers also get `run_code` outside their tool
  filter and are not read-only: do not dispatch; ask the user to switch to
  native presentation.
- Under native presentation reviewers get only `read`, `grep` and `glob`, cannot
  delegate (depth 1) and run with the `never` approval policy.
- `dsh --profile headless` is the designed path: there the tool rows sit beside
  dsh's own delegation tools. In `dsh web` the host plane's tools are inherited
  by preset agents in source, but this is not verified at runtime; the
  `minimal` preset has no read/grep/glob tools, so delegation fails there.
- At most 8 subagents run at once per session (`maxActiveSubagents`); a ninth
  start fails with `ACTIVATION_LIMIT_REACHED` instead of queueing. Start a wave
  of up to 8 roles in one assistant message, then the rest.
- Results: a call returns `started subagent <id>` and the answer arrives as a
  completion notice (0.2.1 source; older releases may instead wait and return
  the answer). Either way, a role without its JSON answer is incomplete.
- Track progress with `todo_write`. The `schedule_*` tools exist only in `dsh web`;
  elsewhere, for the post-PR check use one bounded `sleep 300 && gh pr view …` or
  tell the user the check is still due.
- If `deepseek-official` is not configured or rejects the model or effort, stop
  that role and report it; never substitute silently. Record per role the tool,
  model, effort, tokens and duration, as on the other runtimes.
