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

If a workspace-manager skill is installed (for example task-workspaces, `wsp`),
load it and follow its own instructions to create, resume and release the task
tree, including any sparse-checkout profile it offers. Use only the absolute
paths it returns, and never edit or switch the canonical checkout.

Without a configured manager, reuse a verified task checkout or create an
isolated tree using the host's supported workflow (for example Claude Code or
Codex worktrees). Never switch the branch of a checkout another task may be using.
