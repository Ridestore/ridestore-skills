# Install, update and verify the package

Keep the whole `pr-shepherd` directory together: `SKILL.md` metadata holds the
version, and `references/`, `agents/` and `scripts/` belong to that version.
The canonical source is `plugins/pr-shepherd/skills/pr-shepherd` in
[Ridestore/ridestore-skills](https://github.com/Ridestore/ridestore-skills).

## Install

The plugin is the recommended install; it ships the package and registers the
five Claude reviewer definitions:

```sh
claude plugin marketplace add Ridestore/ridestore-skills
claude plugin install pr-shepherd@ridestore-skills
codex plugin marketplace add Ridestore/ridestore-skills
codex plugin add pr-shepherd@ridestore-skills
```

To work on the package itself, link a clone instead of installing the plugin
(never both in one runtime, or everything is registered twice):

```sh
python3 scripts/install.py --dry-run    # plan
python3 scripts/install.py --install    # link
python3 scripts/install.py --check      # 0 linked, 1 missing, 2 collision/invalid
```

Defaults: `~/.agents/skills/pr-shepherd` for Codex (pass `--codex-root
~/.codex/skills` on hosts that use it), `~/.claude/skills/pr-shepherd` for
Claude, and one link per `agents/*-reviewer*.md` under `~/.claude/agents`.
For OpenCode add `--opencode-root ~/.config/opencode/agents` to link
`agents/opencode/*.md`; the remote skill index delivers the skill text but
cannot register agents, so OpenCode reviewers always need this step. For
DeepSeek Harness add `--dsh-home ~/.dsh` (or `$DSH_HOME`): it links the skill to
`<dsh-home>/skills` and keeps the reviewer tools from `agents/dsh/cordis.patch.yml`
in a marked block of `<dsh-home>/cordis.patch.yml`, leaving the rest of that
file alone ([dsh matrix](dsh-models.md)). Every
root can be explicit, and `--source` picks another complete package. The
installer fetches nothing, is idempotent, and refuses to overwrite files or
links it did not create; reconcile a collision by hand.

## Reviewer definitions

`agents/opus-reviewer-medium.md`, `opus-reviewer.md`, `opus-reviewer-xhigh.md`,
`sonnet-reviewer.md` and `sonnet-reviewer-xhigh.md` pin `claude-opus-5-5` /
`claude-sonnet-5-5` at medium, high or xhigh, with only Read/Grep/Glob. Do not widen their tools. A role that needs
another model or effort needs its own definition: add the file, reference it in
`references/claude-models.md`, add it to the plugin's `agents` list, then run
`python3 scripts/check_matrix.py --plugin-manifest <plugin.json>`.

## Changing models and "last verified"

1. Check the new model and effort against current official docs.
2. Run a bounded real probe: one native review call per definition (Claude) or
   per model/effort (Codex). Keep the observed response model, tokens and result;
   self-reports and init metadata are not evidence.
3. Update the matrix table and its `Last verified: YYYY-MM-DD — <what ran>` line.
   Say which combinations ran and which are policy only.
4. Run `check_matrix.py`; it fails on pin mismatches and warns when a matrix was
   last verified more than 60 days ago (`--strict` makes that an error).
5. Bump `metadata.version` and the plugin manifests, add a changelog entry,
   start a fresh session before relying on new discovery.

If a pinned model is unavailable, keep the requested version and report the
failure; never substitute an alias or Haiku silently. Codex and Claude matrices
are separate; changing one does not authorize changing the other.

## Evals

`plugins/pr-shepherd/evals/` holds `claude plugin eval` cases for the decisions
that must not regress (no push before review, exemptions, no attestation for an
incomplete review, asking about product decisions). They make real model calls:

```sh
claude plugin eval plugins/pr-shepherd --runs 1 --max-cost-usd 5 --no-publish
```
