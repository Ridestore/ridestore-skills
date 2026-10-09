# Workspace integration

The portable core needs Git access, a task checkout, applicable repository
instructions, verification commands, native review agents and a PR tool.
Repository and user rules choose isolation; this skill does not change them.
Reviewers read the coordinator's frozen tree and do not need writable trees.

When the user's workspace or repository instructions name an isolation manager,
use it and its returned absolute paths, and follow its lifecycle rules. Do not
fall back to a native worktree, a handoff or a plain `git worktree add` when the
manager is required but fails; diagnose it with the manager's own tools and the
workspace's recovery rules. No registry is fabricated when none is configured.

Example: with [task-workspaces](https://github.com/maslowivan/maslow-skills/tree/main/plugins/task-workspaces) (`wsp`):

1. `wsp sparse match "<task scope>" --repo <repo> --json`; select and pass the
   applicable committed profile when the repository provides one.
2. `wsp ensure --task <id> --repo <repo> --profile <repo>:<profile> --branch
   <codex|claude>/<slug> --json`; omit profile only when none is applicable.
   Resume the same ID; use `--from-remote-branch` for an existing PR branch.
3. Use only its returned absolute path. Diagnose a failure with `wsp doctor`.
   Never edit/switch the canonical checkout.
4. Release the task when work stops, following the manager's lifecycle rules.

Without a configured manager, reuse a verified task checkout or create an
isolated tree using the host's supported workflow (for example Claude Code or
Codex worktrees). Never switch the branch of a checkout another task may be using.
