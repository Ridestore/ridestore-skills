# Follow up on the published PR

## Schedule the first check

Record the PR URL, exact pushed SHA, push/open timestamp, monitor owner and
an absolute monitoring deadline (default: 90 minutes after monitoring starts,
unless the user/workspace specifies another limit). Arrange an
inspection about five minutes later. Use a native asynchronous wakeup,
recurring heartbeat or bounded non-blocking wait. Do not block communication
with a five-minute shell sleep. Read-only useful work may continue meanwhile.

- **Codex:** use the available heartbeat/thread-wakeup tool. Search existing
  task monitors first and update the matching monitor instead of duplicating
  it. Save the exact repository/PR/head, five-minute first due time and this
  procedure in human-readable form. Keep it quiet while nothing actionable
  changes; notify on a finding, failure, completion or required user action.
- **Claude Code:** use the running version's available native scheduling or
  background task tools. Do not assume Codex automation APIs exist in Claude.
  If no wakeup exists, remain in the session with short non-blocking waits,
  checking elapsed time and keeping the user informed. If the session cannot
  stay active, explain that the mandatory check is still outstanding; never
  promise a monitor that was not actually scheduled.

Use the repository's or workspace's stricter monitoring cadence/readiness
rules when present (for example shorter check intervals or a different absolute
window). Neither a poll, API error, new head nor an authorized fix/push extends
the deadline. Do not create a replacement monitor to evade it; another window
requires the user's explicit request. The approximately-five-minute default
does not erase those standing rules.

Before creating or resuming a monitor, inspect existing automations and active
chat turns. Keep one owner per repository/PR. Verify the live exact-head
completion gate below before starting another review loop; an open PR alone
is not reason to restart completed monitoring.

## Inspect the live head, not an old success

Use GitHub tools or authenticated `gh`/API calls. Re-read current PR state,
`headRefOid`, base branch, `mergeStateStatus`, reviews and checks; compare the
head with the remote branch. If another actor pushed a different head, revoke
the stale local-review attestation and inspect its diff before claiming this
skill reviewed it. Preserve the other actor's work.

On every wakeup, read the live PR state first. For `MERGED` or `CLOSED`, pause
the task-specific monitor immediately and verify its paused state; do not
inspect old threads, push fixes or transition to deployment monitoring.

Inspect all of these with complete pagination:

1. Review summaries, verdicts and any `CHANGES_REQUESTED` reviews; record the
   commit each automation report actually reviewed.
2. Inline review threads, including `isResolved`, `isOutdated`, path/line,
   original commit and all replies. GraphQL `reviewThreads` provides thread
   state; a list of REST review comments alone is insufficient. Paginate both
   threads and nested comments when needed.
3. Top-level PR comments, especially automatic reports not represented as
   formal reviews.
4. Check runs/status contexts, required checks, failures, warnings and
   annotations. Retrieve failed job logs when needed to diagnose a failure.
5. Merge conflicts or branch-policy constraints affecting the current head.

Old/outdated findings may still describe a bug in the current code; inspect
the original hunk and current logic. A remapped comment `commit_id` does not
prove the comment was authored on the newest head. An old approval does not
approve new code.

## Respond, repair and resolve

The invoking workflow authorizes replies on this task's PR and resolution of
addressed review threads. It does not authorize approval, merge, deployment,
messages elsewhere or changing repository-wide review settings.

- For a valid in-scope finding: fix it locally, add useful regression coverage,
  run applicable checks, complete local review for the resulting head (a
  substantial fix gets the fresh full-diff pass, local-review.md item 7), then
  push. Reply in the original thread with the fix commit and verification.
  Resolve the thread only after the fix is present remotely.
- Triage automated review comments the same way as local findings
  ([stop rule](local-review.md#4-reconcile-and-fix)). Batch the blocking ones
  (by consequence, local-review.md item 8) into one fix and one review round.
  In rounds 1 and 2, fix every valid comment. From round 3, a valid but
  non-blocking comment (minor precision, rare edge case, wording) gets a reply with the one-line reason it is left as is, is added to
  the PR body's known limits, and is resolved; it does not start a new round.
- For an incorrect or already-fixed finding: reply with concrete source or
  reproduction evidence, then resolve the addressed thread. Do not resolve
  solely because GitHub marks it outdated or the author calls it a nit.
- For a product decision, ambiguity or out-of-scope change: explain the issue
  on the PR, ask the user a focused question and leave the thread unresolved
  until an agreed resolution is implemented or evidenced.
- Top-level comments/review summaries cannot always be marked resolved; reply
  with their dispositions and track any blocking item. Do not claim a
  formal `CHANGES_REQUESTED` review was dismissed just because its inline
  threads were resolved. Inspect/request the normal automation re-review as
  appropriate; never self-approve or fabricate another reviewer's approval.
- Inspect every warning, including small findings. Fix relevant CI failures;
  classify an external failure only using concrete evidence, with an explicit
  remaining-risk report. Do not blindly rerun checks to hide a code failure.

Every new push requires a delayed inspection of that SHA within the existing
deadline. Update the existing monitor; do not create competing polling owners
or reset the window.

## Completion gate

When the repository has review automation, an effective, non-dismissed
approval of the live exact head by it plus **every** inline thread resolved
(including outdated threads) completes review follow-up, even while waiting for
a human merge. Pause and verify review-only monitoring. Record the repository,
PR, head, approval URL/ID, verification time, thread result and monitor states
wherever the workspace keeps completion records, when it has one. Recheck live evidence before using
that record. A changed head, new/reopened unresolved thread or superseded
approval invalidates the relevant completion; a later routine intake does not.
If CI work remains, remove review dispatch from the existing monitor and keep
only that unfinished CI scope within the original deadline.

One completed delayed inspection of the **latest head** is the minimum. End
this skill's follow-up when the expected review automation has responded for
that head, applicable checks have finished successfully (or a documented
external risk has been explicitly accepted where required), there are no
unresolved blocking review findings (known limits listed separately), and local verification/worktree state
are clean. A stricter repo readiness loop still applies. If a repository
explicitly has no automatic reviewer, record that verified configuration;
silence by itself does not prove review is disabled.

`QUEUED`, `IN_PROGRESS`, `PENDING`, `Awaiting build to finish` and cancelled
`No deployment webhook received` placeholders are unresolved states, not
passed tests. If one remains, report prominently: the exact check name,
status/summary, whether tests ran, `mergeStateStatus` and the next action.
Keep relevant unresolved checks in progress until success or explicit user
acceptance; do not call the PR fully green/ready/complete in the meantime.

At completion, pause/remove the task-specific monitor, retain the review
record and report the PR URL plus checks and remaining limitations. No
perpetual polling is needed after a clean completed follow-up unless asked.

At the absolute deadline, pause the monitor and verify its state even if work
is unfinished. Record unresolved checks/reviews and the next action, and notify
the user once. A stopped monitor does not mean the PR or coding task is ready.
