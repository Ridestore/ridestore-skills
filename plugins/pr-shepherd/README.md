# pr-shepherd

Takes a coding task from request to a **normal (non-draft) pull request that has
already passed a local multi-agent review**. Independent read-only reviewer
agents check the change **before the first push**. The agent fixes every
confirmed finding, opens the PR with the review evidence, then comes back to
handle review threads and CI.

It works in any GitHub repository, in **Claude Code** and **Codex** (and in
OpenCode as a plain skill).

## Usage

```
/pr-shepherd:pr-shepherd <what to do>     # Claude Code, plugin install
/pr-shepherd <what to do>                 # Claude Code, skill linked directly
$pr-shepherd <what to do>                 # Codex
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
4. **Local multi-agent review.** Read-only reviewers inspect one frozen snapshot
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

   Basic, Standard and Deep tiers decide which roles run. The coordinator
   verifies each finding against the source, fixes the confirmed ones and
   re-reviews until nothing actionable is left. A reviewer that didn't return
   means the review is incomplete, not approved.
5. **Publish.** Pushes only the reviewed head and opens a normal PR. The PR body
   records the reviewed SHAs, which roles and models actually ran, the checks
   and any limitations.
6. **Follow up.** About five minutes after the PR opens, it reads review
   threads, comments and checks. It fixes what is actionable (with another
   local review before each push), replies with evidence and resolves the
   threads it addressed. It stops on merge, close or the deadline (90 minutes
   by default).

It never merges or deploys unless you say so separately.

## Reviewer models

| Runtime | How reviewers run |
| --- | --- |
| Claude Code | Two native subagents shipped with the plugin: `opus-reviewer` (`claude-opus-5-5`) and `sonnet-reviewer` (`claude-sonnet-5-5`), both at high effort and limited to Read/Grep/Glob. As a plugin they appear as `pr-shepherd:opus-reviewer` and `pr-shepherd:sonnet-reviewer`. |
| Codex | Native Codex subagents: mostly `gpt-6.1-sol` at high effort, `gpt-6-luna` at xhigh for types, code quality, language and verification, `gpt-6-astra` at medium for security. |

Full role-to-model tables:
[`claude-models.md`](skills/pr-shepherd/references/claude-models.md),
[`codex-models.md`](skills/pr-shepherd/references/codex-models.md).

## Configure it per repository

Defaults work without configuration. To adapt the skill, write rules in the
repository's `AGENTS.md` / `CLAUDE.md` (or in your workspace's instructions):

| Setting | Example |
| --- | --- |
| Worktree manager | "Create task trees only with task-workspaces (`wsp ensure`)." |
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

OpenCode and updates: see the [repository README](../../README.md#install).

If you work on the skill itself, don't install the plugin. Clone this repository
and link the package with its installer instead:

```sh
python3 plugins/pr-shepherd/skills/pr-shepherd/scripts/install.py --dry-run
python3 plugins/pr-shepherd/skills/pr-shepherd/scripts/install.py --install
```

It links the skill into Claude Code (`~/.claude/skills`) and Codex
(`~/.agents/skills`; pass `--codex-root ~/.codex/skills` for the older location)
and the two reviewer definitions into `~/.claude/agents`. It refuses to
overwrite anything it didn't create. Don't combine it with the plugin in the
same runtime, or everything is registered twice. Details are in
[`maintenance.md`](skills/pr-shepherd/references/maintenance.md).

## Files

```
skills/pr-shepherd/
  SKILL.md                    the workflow (version in metadata)
  agents/openai.yaml          Codex skill metadata
  agents/*-reviewer.md        the two Claude reviewer definitions
  references/
    local-review.md           freezing the snapshot, review packet, fix loop, pass gate
    roles.md                  roles and Basic / Standard / Deep routing
    claude-models.md          Claude role-to-model matrix
    codex-models.md           Codex role-to-model matrix
    progress.md               visible progress while agents run
    post-pr.md                follow-up on threads and checks after the PR
    attestation.md            optional marker + label for review automation
    workspaces.md             isolation managers
    maintenance.md            installing, updating, changing models
  scripts/install.py          link installer for development copies
```
