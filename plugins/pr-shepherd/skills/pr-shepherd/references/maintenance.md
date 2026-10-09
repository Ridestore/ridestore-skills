# Install and update the shared package

Keep the entire `pr-shepherd` directory in one trusted source location.
`SKILL.md` metadata records its version; the `references/`, `agents/` and
`scripts/` directories belong to that same version. Distributing only SKILL.md
loses the review protocol, model profiles and native agent definitions.

The canonical source is `plugins/pr-shepherd/skills/pr-shepherd` in
[Ridestore/ridestore-skills](https://github.com/Ridestore/ridestore-skills).
The recommended install is the plugin from that marketplace; it ships the whole
package and registers both Claude reviewer definitions:

```sh
claude plugin marketplace add Ridestore/ridestore-skills
claude plugin install pr-shepherd@ridestore-skills
codex plugin marketplace add Ridestore/ridestore-skills
codex plugin add pr-shepherd@ridestore-skills
```

Do not combine a plugin install with linked copies in the same runtime: the skill
and the reviewers would be registered twice. To work on the package itself, use
a clone of the repository as the trusted source and link it with the installer
below instead of installing the plugin.

The standard-library Python installer links this complete source into both
runtimes and registers the two native Claude reviewer definitions. It fetches
nothing and changes nothing until `--install` is explicit:

```sh
python3 /path/to/pr-shepherd/scripts/install.py --dry-run
python3 /path/to/pr-shepherd/scripts/install.py --install
python3 /path/to/pr-shepherd/scripts/install.py --check
```

Defaults are `~/.agents/skills/pr-shepherd` for Codex,
`~/.claude/skills/pr-shepherd` for Claude, and two Markdown links beneath
`~/.claude/agents`. On an existing Codex host that uses `~/.codex/skills`, pass
`--codex-root ~/.codex/skills` to each command. All roots can be explicit:

```sh
python3 /path/to/pr-shepherd/scripts/install.py --dry-run \
  --codex-root /chosen/codex/skills \
  --claude-root /chosen/claude/skills \
  --claude-agents-root /chosen/claude/agents
```

`--source /trusted/pr-shepherd` selects another complete source. The JSON
report names the source version, resolved destinations and pinned models.
`--check` is read-only: exit 0 means every link resolves to this source; exit 1
means links are missing; exit 2 means a collision or invalid source. Dry-run
shows planned links without creating directories. Installation is idempotent.
Existing files, directories and links to other sources are unmanaged collisions;
the installer preflights all targets and refuses to overwrite them. Inspect and
explicitly reconcile a collision before retrying. Do not remove a user's
existing installation automatically.

## Native Claude definitions and model updates

The authoritative Claude selectors are in
[`opus-reviewer.md`](../agents/opus-reviewer.md) and
[`sonnet-reviewer.md`](../agents/sonnet-reviewer.md).
They pin `claude-opus-5-5` and `claude-sonnet-5-5`, both at `effort: high`,
with only Read/Grep/Glob.
Invoke the installed native `subagent_type` with the role-specific frozen
packet; omit a per-call model override, which would override the definition.
The role matrix maps duties to these definitions. Separate execution evidence
requires an expressly bounded agent and tools; do not widen these reviewers.

To update, edit or replace the complete source **at the same source path**,
bump `metadata.version` and its update date, and keep model matrices,
definitions and instructions consistent. The links immediately expose the
same version in both runtimes. Run `--check`, inspect its reported pins, and
start a fresh runtime session before relying on updated discovery. If moving
the source path, inspect the old links and explicitly reconcile them; the
installer will not repoint existing unmanaged links.

Validate a changed model with current official documentation and a bounded
actual runtime probe before adopting it. Record the requested selector,
actual response model, provider, tool IDs, results and reported cost separately.
For native reviewer validation, retain actual child `message.model` evidence
linked by `parent_tool_use_id`. Initialization metadata and self-reports alone
are insufficient. Opus 5.5 and Sonnet 5.5 generated actual responses on the
tested Claude 2.1.285 installation; other hosts must verify their own access.
If a pinned model is unavailable, preserve the requested version and report the
failure. Never silently substitute aliases or Haiku. Codex and Claude model
profiles remain separate; changing one does not authorize changing the other.
