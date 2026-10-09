# ridestore-skills

Agent workflow plugins for **Claude Code**, **Codex** and **OpenCode**, published by
Ridestore and usable in any GitHub repository. The repository is a plugin
marketplace for Claude Code and Codex and a remote skill source for OpenCode.
Every plugin ships the same skills to all three agents; `pr-shepherd` also
installs into DeepSeek Harness (`dsh`) from a clone. Company- or team-specific
rules stay out of the skills; you add them in your repository's `AGENTS.md` /
`CLAUDE.md`.

## Plugins

| Plugin | Claude Code | Codex | OpenCode | DeepSeek Harness | What it does |
| --- | :-: | :-: | :-: | :-: | --- |
| [pr-shepherd](plugins/pr-shepherd) | ✓ | ✓ | ✓ | ✓ | Implement a task and open a normal PR only after independent read-only reviewer agents (bugs, architecture, types, security, …) have reviewed it on pinned models before the first push; then follow up on review threads and CI. Optional attestation label for your review automation. [Details →](plugins/pr-shepherd) |

## Install

### Claude Code

```sh
claude plugin marketplace add Ridestore/ridestore-skills
claude plugin install pr-shepherd@ridestore-skills
```

Update later with `claude plugin marketplace update ridestore-skills` and
`claude plugin update <plugin>@ridestore-skills`, or through `/plugin` inside a session.

### Codex

```sh
codex plugin marketplace add Ridestore/ridestore-skills
codex plugin add pr-shepherd@ridestore-skills
```

Update later with `codex plugin marketplace upgrade ridestore-skills`, then
`codex plugin add <plugin>@ridestore-skills` again.

### OpenCode

OpenCode has no plugin marketplace. Instead it loads skills from a URL that
serves an `index.json`. Every plugin publishes one at `plugins/<plugin>/skills/index.json`.
Add it to `opencode.json` (project) or `~/.config/opencode/opencode.json` (global):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "skills": [
    "https://raw.githubusercontent.com/Ridestore/ridestore-skills/main/plugins/pr-shepherd/skills/"
  ]
}
```

OpenCode caches the skills and downloads them again when the plugin version
changes. Plugins that ship subagents (like `pr-shepherd`'s reviewers) need one more
step from a clone, because the skills index cannot register agents; see the
plugin's README. If you prefer a local clone, list its path instead:
`"skills": ["~/Projects/ridestore-skills/plugins/<plugin>/skills"]`.

### DeepSeek Harness (dsh)

[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) finds skills
in `~/.dsh/skills` and `~/.agents/skills` and takes configuration from
`~/.dsh/cordis.patch.yml`; it has no marketplace for this repository. Install
from a clone; `pr-shepherd`'s installer links the skill and adds its DeepSeek
reviewer tools:

```sh
python3 plugins/pr-shepherd/skills/pr-shepherd/scripts/install.py --install --dsh-home ~/.dsh
```

Update with `git pull`; re-run the installer when the plugin's changelog says
the reviewer tools changed. See [pr-shepherd's README](plugins/pr-shepherd#deepseek-harness-dsh).

### Only the skill, without a plugin

Every skill is a plain folder at `plugins/<plugin>/skills/<skill>`. You can also
link or copy it into `~/.claude/skills/`, `~/.codex/skills/`, `~/.config/opencode/skills/`
or `~/.dsh/skills/`.
Don't do both for the same skill in one agent, or it is loaded twice. `pr-shepherd`
has its own link installer that also registers its Claude reviewer agents; see its README.

## Layout

```
.claude-plugin/marketplace.json   Claude Code catalog of all plugins
.agents/plugins/marketplace.json  Codex catalog of all plugins
plugins/<plugin>/
  .claude-plugin/plugin.json      Claude Code manifest
  .codex-plugin/plugin.json       Codex manifest
  skills/<skill>/SKILL.md         the skill, shared by all agents
  skills/index.json               OpenCode index (generated)
  README.md                       what the plugin does, setup, usage (required)
  CHANGELOG.md                    one `## <version>` section per release (required)
scripts/validate.sh               checks catalogs, manifests and OpenCode indexes
scripts/build_opencode_index.py   regenerates the OpenCode indexes
scripts/check_versions.py         changed plugins must bump version + changelog (CI)
```

## Adding a plugin

1. Create `plugins/<name>/` with `README.md`, `CHANGELOG.md`, `skills/<skill>/SKILL.md`,
   `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` (`"skills": "./skills/"`).
   Both manifests need the same `name` and `version`.
2. Add an entry to both catalogs: `.claude-plugin/marketplace.json`
   (`"source": "./plugins/<name>"`) and `.agents/plugins/marketplace.json`
   (`"source": {"source": "local", "path": "./plugins/<name>"}`, `"policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL", "products": ["CODEX"]}`, `"category": "Developer Tools"`).
3. Run `python3 scripts/build_opencode_index.py`. Run it again whenever skill files change.
4. Add a row to the table above, linking the plugin name to its folder, then run `scripts/validate.sh`.

**Releases.** Every change to a plugin must bump `version` in both manifests
and add a `## <version>` section to the plugin's `CHANGELOG.md`. If either is
missing, CI fails. When the change lands on `main`, CI tags it `<plugin>-v<version>`
and publishes a GitHub release.

## License

[MIT](LICENSE)
