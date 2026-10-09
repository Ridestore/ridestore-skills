# Changelog

## 2.0.0

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
