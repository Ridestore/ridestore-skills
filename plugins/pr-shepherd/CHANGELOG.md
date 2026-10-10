# Changelog

## 2.5.1

- A substantial review fix (a new mechanism such as a parser, cache or retry
  scheme, or a rewrite of a meaningful part of the change) gets a fresh
  full-diff pass by Felix plus the specialists the new code signals, not only
  Maya's incremental check.
- Stop rule: from the third review round on, only blocking findings
  (critical or important with a plausible trigger) are fixed; the rest are
  recorded as known limits in the review record and PR body. Automated review
  comments after the PR is open are triaged the same way: non-blocking ones
  get a reply with the reason and are resolved without a new round. Repeated
  blocking findings in code the previous round wrote are treated as a design
  problem to simplify, not patch.

## 2.5.0

- Ruby (performance), Oscar (code quality) and Iris (language) are routed by
  signals in the diff, like Remy+: `review_packet.py` adds each one to the plan
  when changed code or config has a signal for it and records the matches in the
  manifest (`specialists`) and `self-check.md`
  ([routing](skills/pr-shepherd/references/roles.md#routing)). Docs, tests,
  fixtures, lockfiles, generated output, translations and release metadata are
  ignored, and a fix check routes on the changes since the reviewed head.
  `--specialist-signal ROLE:NAME=REGEX` adds repository signals, matched
  against changed paths and added lines. Same for every
  runtime.
- The packet's diff reader counts hunk lengths, so a content line starting with
  `++ ` no longer hides the rest of a file from security or specialist signals;
  file names with spaces or non-ASCII characters keep their path, and renames
  and binary files count by path. Diffs are read as bytes with fixed git output
  (no colour, external diff tool, custom prefixes or line indicators), so a lone carriage return
  or the user's git config cannot shift hunks. Specialist signals scan lines up
  to 2,000 characters and every pattern is bounded, so a minified line cannot
  stall the script; security signals still scan whole lines. Both the full and
  the fix diff read attributes from the merge base (`--attr-source`, git
  2.40+), so a `.gitattributes` added by the PR cannot hide its own lines. An
  added `.gitattributes` line that can hide or collapse source (`-diff`,
  `binary`, `filter=` such as LFS, `linguist-generated`, a macro) on a pattern
  that is not an asset, map, snapshot or generated output (on lockfiles and
  minified bundles only `linguist-*` is harmless), a file git still shows as
  binary that is not such an asset or output (committed `dist/` bundles,
  lockfiles and minified files count), and a committed key, certificate or
  credential file (`.env`, `.npmrc`, `.netrc`, `.aws/credentials`, Terraform
  state and tfvars, kubeconfig, keytabs, service-account JSON),
  also under tests, route Remy+.
- Repository signals (`--security-signal` and `--specialist-signal`) are
  recorded as `repo: NAME`: they add to the built-in signals and can no longer
  replace or switch one off. An invalid regex stops with the offending item.

## 2.4.2

- Claude: Opus only for Maya (bugs) and Remy+ (sensitive security); Theo and
  Felix move to `sonnet-reviewer-medium`, so the independent pass also runs on a
  different model than the bug review.
- Codex: GPT-6.1 Sol only for Maya (medium) and Remy+ (high); Finn, Theo,
  Jasper, Felix, routine Remy, Ruby, Zoe, Cleo, Otis, Milo and Luna run GPT-6
  Luna at xhigh; Nora, Oscar, Iris and Vera stay on Luna at high.
- OpenCode follows Codex for its GPT roles: Sol (high) only for Remy+; Maya, Zoe
  and Cleo stay on Claude Opus. It brings back `pr-shepherd-luna-xhigh` and
  retires `pr-shepherd-sol`, which the installer removes when it created it. A
  `pr-shepherd-luna-xhigh.md` left from before 2.4.0 that the installer cannot
  attribute to itself is reported as a collision; remove it by hand.

## 2.4.1

- Explicitly identify `task-workspaces` and its `task-workspaces:task-workspaces`
  alias in workspace integration guidance, directing agents to its SKILL.md.

## 2.4.0

- DeepSeek Harness (dsh) support: `install.py --dsh-home ~/.dsh` links the skill
  and adds two read-only reviewer tools (`pr_shepherd_flash` at high,
  `pr_shepherd_flash_max` at max) to dsh's home patch in a managed block;
  `review_packet.py --runtime dsh`, a dsh matrix (`references/dsh-models.md`) and
  `check_matrix.py` checks for it. DeepSeek Flash for every role; not yet
  verified at runtime.
- No more GPT-6 Astra: Remy+ (sensitive security) runs GPT-6.1 Sol at high in
  Codex and OpenCode, one step above routine Remy. The OpenCode agent
  `pr-shepherd-astra` is replaced by `pr-shepherd-sol-high`.
- OpenCode DeepSeek fallback uses `deepseek-flash` for every role (no V4-Pro).
- Faster reviews: every role runs one effort step lower (Deep-review roles at
  high/xhigh took 6–8 minutes each). Claude: Opus never above medium
  (`opus-reviewer-medium` for Maya, Theo, Felix and Remy+), Sonnet at medium
  (new `sonnet-reviewer-medium`) for Finn, Jasper, routine Remy, Ruby, Vera,
  Otis, Milo, Luna, Zoe and Cleo, Sonnet at high for Nora, Oscar and Iris;
  `opus-reviewer`, `opus-reviewer-xhigh` and `sonnet-reviewer-xhigh` are removed.
  Codex/OpenCode: Sol at medium, Luna at high, Remy+ on Sol at high (OpenCode
  agents `pr-shepherd-sol` now medium, `pr-shepherd-luna-high`,
  `pr-shepherd-sol-high`). dsh: every role at high, Remy+ at max.
- The installer removes its own retired files (old `opus-reviewer` and xhigh Claude links,
  `pr-shepherd-astra`, `pr-shepherd-sol-medium`, `pr-shepherd-luna-xhigh`) and
  leaves anything it did not create.
- Workspaces: no hard-coded manager commands or links; if a workspace-manager
  skill is installed, the skill loads it and follows its instructions.
- `review_packet.py` writes a per-role `label` for the agent call's description:
  name, what it checks, model and effort ("Maya · Bugs review · Opus medium").

## 2.3.1

- OpenCode fallback models updated: DeepSeek Flash (`deepseek-flash`) for every
  role and DeepSeek V4-Pro only for sensitive security (Remy+); GLM-5.3 for GLM.

## 2.3.0

- OpenCode provider fallback: when neither GPT (OpenAI) nor Claude (Anthropic) is
  connected, `install.py --opencode-root` installs the reviewer agents on DeepSeek
  models (reasoner for deep roles, chat for the rest), or else on GLM. Detection
  reads API-key variables, OpenCode logins and config; `--opencode-profile`
  overrides. Single-family profiles are flagged as not cross-family.

## 2.2.0

- Codex: Maya (bugs) and Theo (architecture) run GPT-6.1 Sol at medium, as in the
  production reviewer's normal policy, instead of high. OpenCode: Theo uses a new
  `pr-shepherd-sol-medium` agent. Speed over one effort step for the two slowest roles.

## 2.1.0

- Claude: Maya (bugs) and Theo (architecture) run Opus 5.5 at medium effort
  through a new `opus-reviewer-medium` definition, one step lower than before;
  they were the slowest roles at high. Codex is unchanged (GPT-6.1 Sol at high).

## 2.0.0

- Self-check before dispatch: `scripts/review_packet.py` freezes the snapshot,
  exports the full diff, lists the instruction files, reports values the change
  replaced that are still present (`--stale`) and writes one prompt per role.
- Less reviewer overlap: every role states what it leaves to others; doc-heavy
  changes run Finn and Jasper as one call; `scripts/merge_findings.py` groups the
  same issue across roles and flags unfinished or stale-head reviewers. Progress
  updates and the PR body show each role's tokens and duration.
- Two more Claude reviewer definitions at xhigh effort (`opus-reviewer-xhigh`,
  `sonnet-reviewer-xhigh`) for the roles that run at xhigh on Codex; the installer
  discovers every `agents/*-reviewer*.md`.
- Model matrices carry a `Last verified` line; `scripts/check_matrix.py` checks
  definitions against the tables and flags old verifications (run in validation).
- `claude plugin eval` suite with four cases; script tests run in CI.
- `SKILL.md` is about 40% shorter and says which reference to read when.
- Security reviewer tiers: Remy runs on GPT-6.1 Sol/high (Claude: Opus/high)
  for routine security checks and on Remy+ (GPT-6 Astra at medium at most;
  Claude: Opus/xhigh) for authentication, authorization, trust boundaries,
  secrets, infra permissions, production commerce APIs (commercetools),
  payments, stored personal data or cross-service changes; repositories can add
  their own signals with `--security-signal`. `review_packet.py` picks
  the tier from signals in changed code and config (docs and tests ignored) and
  records the matches; the coordinator may raise it, never lower it.
- OpenCode support: four reviewer agents in `agents/opencode/` with mixed
  providers (Felix's independent pass on a different model family than Maya),
  `references/opencode-models.md`, `review_packet.py --runtime opencode`,
  `install.py --opencode-root`, and matrix checks. Not yet verified at runtime.

- Renamed from `ridestore-task` to `pr-shepherd` and made it work in any GitHub
  repository. Invocation is now `/pr-shepherd` (`/pr-shepherd:pr-shepherd` as a
  plugin) and `$pr-shepherd`.
- Reviewer agents renamed to `opus-reviewer` and `sonnet-reviewer`
  (`pr-shepherd:opus-reviewer`, `pr-shepherd:sonnet-reviewer` as a plugin).
- Company- and workspace-specific rules moved out of the skill. Repository and
  workspace instructions now supply them: isolation manager, verification
  commands, editorial review exemptions, review automation, monitoring limits.
- The review-economy protocol became the optional, generic
  [local-review attestation](skills/pr-shepherd/references/attestation.md). It is
  off unless repository instructions name a label; marker
  `<!-- local-review:v1 … -->`, or a prefix the repository names.
- Review roles keep their names (Finn, Maya, Theo, Felix, …).
- Codex matrix now follows a production reviewer's normal per-role models one
  reasoning-effort step higher: mostly `gpt-6.1-sol`/high, `gpt-6-luna`/xhigh for
  types, code quality, language and verification, `gpt-6-astra`/medium only for
  security. `gpt-6-luna` never runs below high effort.
- Claude reviewer definitions pin `effort: high`; the Claude matrix shows effort per role.
- Published in the `ridestore-skills` marketplace for Claude Code and Codex, and
  as an OpenCode skill index; the Claude plugin registers both reviewer agents.

## 1.1.0

- Last version as `ridestore-task`, before it moved to this repository.
