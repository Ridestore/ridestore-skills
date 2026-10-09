# pr-shepherd

Takes a coding task from request to a **normal (non-draft) pull request that has
already passed a local multi-agent review**. Independent read-only reviewer
agents check the change **before the first push**. The agent fixes every
confirmed finding, opens the PR with the review evidence, then comes back to
handle review threads and CI.

It works in any GitHub repository, in **Claude Code**, **Codex**, **OpenCode**
and **DeepSeek Harness** (`dsh`).

## Usage

```
/pr-shepherd:pr-shepherd <what to do>     # Claude Code, plugin install
/pr-shepherd <what to do>                 # Claude Code, skill linked directly
$pr-shepherd <what to do>                 # Codex
/pr-shepherd <what to do>                 # DeepSeek Harness
```

A plain request that asks for this workflow also triggers it.

## What it does

1. **Start.** Shows the skill version, runtime and a short plan. Reads the
   repository's `AGENTS.md` / `CLAUDE.md` / `REVIEW.md` and inspects the branch,
   PR state and dirty files. Works in an isolated task tree, never in a checkout
   another task may be using.
2. **Implement and validate.** Runs the repository's real lint, type, test and
   build commands. A check that didn't run is reported, not counted as passed.
3. **Classify the whole PR.** Small prose-only changes, editorial content the
   repository declares as such, and literal image URL swaps can skip the
   multi-agent review. Everything else goes through it.
4. **Self-check.** `scripts/review_packet.py` freezes the snapshot and writes a
   self-check: values the change replaced that still appear (`--stale`), the
   instruction files to satisfy, and a short list of usual gaps (missing doc
   updates, logs that don't report what's actually sent). These get fixed
   before any reviewer runs, so reviewers spend their time on real problems.
5. **Local multi-agent review.** Read-only reviewers inspect one frozen snapshot
   (base, head and tree SHAs) of the complete PR diff. Each one has a role:

   | Role | Focus |
   | --- | --- |
   | Finn | the repository's written rules |
   | Maya | concrete bugs; later, checks every fix |
   | Theo | architecture, contracts, side effects |
   | Nora | runtime types and validation at boundaries |
   | Jasper | comments versus actual behavior |
   | Felix | an independent second review that doesn't see the others' findings |
   | Remy, Ruby, Oscar, Iris | security, performance, code quality, language specifics, when the diff needs them |
   | Vera, Otis, Milo, Luna, Zoe, Cleo | verify findings, check facts and reachability, reconcile conflicting findings |

   Basic, Standard and Deep tiers decide which roles run. Each prompt names the
   role's scope **and what to leave to other roles**, and doc-heavy changes run
   Finn and Jasper as one call, so the same issue isn't paid for five times.
   `scripts/merge_findings.py` merges the replies, groups the same issue across
   roles and flags reviewers that didn't finish. The coordinator verifies each
   finding against the source, fixes the confirmed ones and re-reviews until
   nothing actionable is left. A reviewer that didn't return means the review is
   incomplete, not approved.
6. **Publish.** Pushes only the reviewed head and opens a normal PR. The PR body
   records the reviewed SHAs, which roles and models actually ran with their
   tokens and duration, decisions you made along the way, the checks and any
   limitations.
7. **Follow up.** About five minutes after the PR opens, it reads review
   threads, comments and checks. It fixes what is actionable (with another
   local review before each push), replies with evidence and resolves the
   threads it addressed. It stops on merge, close or the deadline (90 minutes
   by default).

It never merges or deploys unless you say so separately.

## Reviewer models

| Runtime | How reviewers run |
| --- | --- |
| Claude Code | Three native subagents shipped with the plugin, limited to Read/Grep/Glob: `opus-reviewer-medium` (`claude-opus-5-5` at medium) for bugs, architecture, the independent pass, sensitive security, verification and the evidence roles, `sonnet-reviewer-medium` (`claude-sonnet-5-5` at medium) for guidelines, comments, routine security and performance, and `sonnet-reviewer` (Sonnet at high) for types, code quality and language. Opus never runs above medium. As a plugin they appear as `pr-shepherd:opus-reviewer-medium` and so on. |
| Codex | Native Codex subagents: mostly `gpt-6.1-sol` at medium effort, `gpt-6-luna` at high for types, code quality, language and verification, Sol at high for sensitive security changes (auth, permissions, trust boundaries, secrets, infra, cross-service), chosen from signals in the diff; routine security checks run on Sol at medium. Efforts are one step lower than before 2.4.0 to keep each reviewer to a few minutes. |
| OpenCode | Four subagents in `agents/opencode/` with mixed providers: Maya, Zoe and Cleo on Claude Opus 5.5, everything else on the Codex models above, so Felix's independent pass runs on a different model family than Maya's. Without GPT or Claude connected, the installer switches the agents to DeepSeek Flash or else GLM-5.3 for every role. Not yet verified at runtime. Parallel reviewers need `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`. |
| DeepSeek Harness (`dsh`) | DeepSeek only: two read-only delegation tools added to dsh's home patch, both on `deepseek-flash` — `pr_shepherd_flash` (effort high) for every role and `pr_shepherd_flash_max` (effort max) for sensitive security (Remy+) only. One model family, so Felix's pass is not cross-family. Not yet verified at runtime. See [DeepSeek Harness](#deepseek-harness-dsh). |

Full role-to-model tables:
[`claude-models.md`](skills/pr-shepherd/references/claude-models.md),
[`codex-models.md`](skills/pr-shepherd/references/codex-models.md),
[`opencode-models.md`](skills/pr-shepherd/references/opencode-models.md),
[`dsh-models.md`](skills/pr-shepherd/references/dsh-models.md). Each one has a
**Last verified** line saying which combinations actually ran and when;
`scripts/check_matrix.py` checks the definitions against the tables and warns
when a matrix hasn't been verified for 60 days.

## Configure it per repository

Defaults work without configuration. To adapt the skill, write rules in the
repository's `AGENTS.md` / `CLAUDE.md` (or in your workspace's instructions):

| Setting | Example |
| --- | --- |
| Worktree manager | "Create task trees only with the installed workspace-manager skill." |
| Verification | "Run `pnpm lint && pnpm test` in `web/`." |
| Editorial exemptions | "Files under `site/src/content/pages/**/*.json` are editorial content." |
| Review automation | "PRs are reviewed by our review bot; its approval of the exact head counts." |
| Attestation | "Local-review attestation label: `autoreviewed-locally`." |
| Monitoring | "Check PRs every 3 minutes; stop after 60 minutes." |

**Attestation** is optional. When it's on, a PR that passed the local review
gets a hidden marker in its body (`<!-- local-review:v1 {"head":…,"base":…,"status":"passed"} -->`)
and the configured label. Your review automation can then trust the local
review, for example by using cheaper models. It never replaces approval, CI or
branch protection. See [`attestation.md`](skills/pr-shepherd/references/attestation.md).

## Install

```sh
# Claude Code (in a session, 2.1.275 or newer)
/plugin install pr-shepherd --marketplace Ridestore/ridestore-skills

# Codex
codex plugin marketplace add Ridestore/ridestore-skills
codex plugin add pr-shepherd@ridestore-skills
```

OpenCode: the skills index from the [repository README](../../README.md#opencode)
delivers the skill, but OpenCode reviewers must be installed from a clone:

```sh
python3 plugins/pr-shepherd/skills/pr-shepherd/scripts/install.py --install \
  --opencode-root ~/.config/opencode/agents
```

DeepSeek Harness: see [below](#deepseek-harness-dsh).

Updates: see the [repository README](../../README.md#install).

If you work on the skill itself, don't install the plugin. Clone this repository
and link the package with its installer instead:

```sh
python3 plugins/pr-shepherd/skills/pr-shepherd/scripts/install.py --dry-run
python3 plugins/pr-shepherd/skills/pr-shepherd/scripts/install.py --install
```

It links the skill into Claude Code (`~/.claude/skills`) and Codex
(`~/.agents/skills`; pass `--codex-root ~/.codex/skills` for the older location)
and the Claude reviewer definitions into `~/.claude/agents`. It refuses to
overwrite anything it didn't create. Don't combine it with the plugin in the
same runtime, or everything is registered twice. Details are in
[`maintenance.md`](skills/pr-shepherd/references/maintenance.md).

## DeepSeek Harness (dsh)

[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (`npm i -g
@deepseek-ai/dsh`, Node 22.19+ or 24+) runs the reviewers on DeepSeek models only.
It has no plugin marketplace for this repository, so install from a clone:

```sh
python3 plugins/pr-shepherd/skills/pr-shepherd/scripts/install.py --install --dsh-home ~/.dsh
```

- **Skill:** linked to `~/.dsh/skills/pr-shepherd`. dsh also reads
  `~/.agents/skills`, so a Codex link there works too.
- **Reviewers:** dsh has no subagent definition files. Instead, each reviewer
  type is a `@deepseek-ai/dsh-tool-subagent` row with its own tool name, pinned
  model and effort. The installer appends the rows from
  [`agents/dsh/cordis.patch.yml`](skills/pr-shepherd/agents/dsh/cordis.patch.yml)
  to `~/.dsh/cordis.patch.yml`, which every dsh profile applies. They go in a
  block between `# >>> pr-shepherd (managed by install.py) >>>` and
  `# <<< pr-shepherd <<<`. Re-running the installer updates only that block
  (atomically, keeping everything else byte for byte), and it refuses files it
  can't append to safely. Because the home patch applies to every profile, the
  two tools appear in every dsh session. If you set `$DSH_HOME`, pass
  `--dsh-home "$DSH_HOME"`.

  | Tool | Model | Effort | Roles |
  | --- | --- | --- | --- |
  | `pr_shepherd_flash` | `deepseek-flash` (V4.1 Flash) | high | every role except Remy+ |
  | `pr_shepherd_flash_max` | `deepseek-flash` | max | Remy+ (sensitive security) |

  DeepSeek's efforts are `off`, `low`, `high` and `max` (no medium).
- **Read-only, with native tool presentation only:** both tools allow only
  `read`, `grep` and `glob`, cap delegation depth at 1 (reviewers can't start
  agents), and inherit dsh's `never` approval policy for children. In PTC
  presentation (the web `ptc` preset or `tools.mode: ptc`) dsh also gives every
  agent `run_code`, outside the tool filter, so the skill refuses to dispatch
  reviewers there.
- **Credentials:** the `deepseek-official` provider reads `DEEPSEEK_API_KEY`
  from the environment, `~/.dsh/.credentials.yaml` or `.env`.
- **Limits:**
  - At most 8 reviewers run at once per session (`maxActiveSubagents`), so the
    coordinator starts them in waves.
  - `dsh --profile headless` is the designed path. In `dsh web` the tools should
    reach preset agents (the host's tools are inherited in source), but that is
    not verified; the `minimal` preset has no read/grep/glob tools at all.
  - `dsh web` reloads the patch live; restart other profiles after installing.
- **Check without running a model:** `dsh --profile headless --dump-config`
  shows the composed tools.

Written against dsh 0.2.0-rc.2 and the 0.2.1 alpha source; not yet verified with
a real review. Run one and update the "Last verified" line in
[`dsh-models.md`](skills/pr-shepherd/references/dsh-models.md).

## Files

```
skills/pr-shepherd/
  SKILL.md                    the workflow (version in metadata)
  agents/openai.yaml          Codex skill metadata
  agents/*-reviewer*.md       the three Claude reviewer definitions (Opus medium, Sonnet medium and high)
  agents/opencode/*.md        the four OpenCode reviewer agents (mixed providers)
  agents/dsh/cordis.patch.yml the two DeepSeek Harness reviewer tools (DeepSeek Flash)
  references/
    local-review.md           freezing the snapshot, review packet, fix loop, pass gate
    roles.md                  roles, what each leaves to others, Basic / Standard / Deep routing
    claude-models.md          Claude role-to-model matrix
    codex-models.md           Codex role-to-model matrix
    opencode-models.md        OpenCode role-to-model matrix and dispatch notes
    dsh-models.md             DeepSeek Harness role-to-model matrix, install and dispatch notes
    progress.md               visible progress while agents run
    post-pr.md                follow-up on threads and checks after the PR
    attestation.md            optional marker + label for review automation
    workspaces.md             isolation managers
    maintenance.md            installing, updating, changing models
  scripts/
    review_packet.py          freeze the snapshot, self-check, write per-role prompts
    merge_findings.py         merge reviewer replies, group duplicates, pass-gate summary
    check_matrix.py           definitions vs matrix tables, "last verified" age
    install.py                link installer (Claude, Codex, OpenCode agents, dsh tools)
tests/test_scripts.py         tests for the scripts (run in CI)
evals/                        `claude plugin eval` cases: no push before review,
                              prose exemption, no attestation when incomplete,
                              asking about product decisions
```

## Evals

The eval cases check the decisions that must not regress. They make real model
calls, so run them on purpose, with a cost cap:

```sh
claude plugin eval plugins/pr-shepherd --runs 1 --max-cost-usd 5 --no-publish
```

Cases with a `fixture.sh` need `--scaffold` (it builds a small git repository in
the eval workspace).
