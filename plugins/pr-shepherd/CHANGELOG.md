# Changelog

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
