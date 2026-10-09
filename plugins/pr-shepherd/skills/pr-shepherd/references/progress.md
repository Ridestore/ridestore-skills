# Progress in the current task

The coordinator owns one visible plan in the current conversation. Use native
plan/task tools when the running host exposes them (Codex plan tool; Claude
TaskCreate/TaskUpdate or TodoWrite). Use only actual tool schemas. If none is
available, maintain the same checklist through concise progress messages.
Do not create GitHub issues, Slack messages, separate user-owned chats or a new
persistent goal just to display progress.

Create phases for implementation, validation, local review, fixes/recheck,
publication and post-PR follow-up. Mark only work actually begun as in progress;
complete each phase only from its result. Mark unnecessary phases skipped with
a reason. A review-only request stops after its authorized review; this plan
does not grant publication authority beyond the user's request.

Before dispatch, show the review tier and role/model plan. Track each planned
role as queued → running → complete, or failed/incomplete. A spawned call is
running, not complete. Keep native child IDs and requested selector, selected
effort, observed runtime model (or explicitly unknown) in the durable review
record. A configured alias, agent's self-report, process launch, or empty output
does not prove model execution. Preserve limitations separately from findings.

Update the visible plan at phase transitions and when a review wave finishes,
a finding needs action, a check fails, or a retry changes the state. During
active implementation/review, provide a concise useful update at least once a
minute; use bounded waits so the coordinator remains responsive. Summarize the
reason for the wait when no new result exists, without inventing progress or a
percentage. Quiet scheduled post-PR polls follow post-pr.md instead.

When a role finishes, show its tokens and duration from the completion report
next to its result, and a running total for the review. The PR body lists them
per role, so the cost of a review is visible.

Example: “Local review: 3/6 roles complete (Maya 220k tokens, 6 min; Nora 99k,
2 min; Finn 165k, 4 min). Maya found an error path; Theo and Nora's results are
being merged.” Show the actual runtime's models and numbers; never copy example
values as execution evidence.

After fixes, reopen the affected review/validation tasks for the new snapshot.
Keep publication pending until the pass or exemption gate succeeds. The PR
phase can finish while follow-up remains active. A timeout or incomplete model
call leaves its phase incomplete. Report completed phases, remaining work and
the exact reason; never turn task completion into an approval signal.
