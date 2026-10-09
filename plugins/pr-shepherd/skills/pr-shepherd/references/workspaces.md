# Workspace integration

The portable core needs Git access, a task checkout, applicable repository
instructions, verification commands, native review agents and a PR tool.
Repository and user rules choose isolation; this skill does not change them.
Reviewers read the coordinator's frozen tree and do not need writable trees.

Use an isolation manager when the user's workspace or repository instructions
name one, or when a workspace-manager skill is installed. Load such a skill and
follow its own instructions to create, resume and release the task tree; use
only the absolute paths the manager returns and follow its lifecycle rules. Do
not fall back to a native worktree, a handoff or a plain `git worktree add` when
the manager is required but fails; diagnose it with the manager's own tools and
the workspace's recovery rules. Never edit or switch the canonical checkout. No
registry is fabricated when none is configured.

If `task-workspaces` is available (possibly listed as
`task-workspaces:task-workspaces`), read its SKILL.md and follow
its instructions for workspace setup and lifecycle.

Without a manager, reuse a verified task checkout or create an
isolated tree using the host's supported workflow (for example Claude Code or
Codex worktrees). Never switch the branch of a checkout another task may be using.
