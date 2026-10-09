# Local review protocol

## 1. Freeze what will be pushed

Finish implementation and applicable verification, then make task-only local
commits. **Local commits are allowed before review; remote pushes are not.**
Never `git add .` in a shared checkout; preserve unrelated work rather than
stashing or committing it blindly. Fetch the target branch (fetching is not
pushing) and build the packet:

```sh
python3 <skill>/scripts/review_packet.py --repo <task tree> --base origin/main --fetch \
  --runtime claude|codex|opencode --roles finn,maya,nora,felix \
  --criteria <file or text> --stale '<old value>' --stale '<old id>'
```

It refuses a dirty tree, records head/tree/target-tip/merge-base SHAs, exports
the **entire** PR diff from the merge base (never just `HEAD~1`), lists the
applicable `AGENTS.md`/`CLAUDE.md`/`REVIEW.md`, writes `self-check.md` and one
prompt per role under `<git-path>/pr-shepherd-review/<head12>/`, outside tracked
source. Without Python, do the same steps by hand.

## 2. Self-check before dispatch

Reviewers are expensive; obvious gaps should not reach them. Before dispatch:

- Pass every value the change replaces as `--stale` (old effort, old model or
  policy ID, renamed function). Each match in `self-check.md` is either fixed or
  confirmed historical.
- Required docs: do the instruction files demand doc or changelog updates for
  this kind of change, and are they in the diff?
- Reporting: do logs, journals and usage records state what is actually sent,
  not what was configured?
- Prose: does every new sentence in docs and comments match the code at head?

Fix what you find, commit, and rebuild the packet. Note the self-check result in
the review record.

## 3. Dispatch

Each reviewer gets its generated prompt: absolute worktree, frozen SHAs, diff and
manifest paths, acceptance criteria, applicable instructions, the role's scope
**and what to leave to others** ([roles](roles.md)), the prohibitions (no edits,
commits, pushes, GitHub comments, nested agents) and the JSON result format.
Felix gets no other findings or author claims. Evidence agents do get the
specific findings. Check live identities before dispatch and again before
accepting results; a changed snapshot invalidates affected results.

If implementation was delegated, finish all writers first, with exclusive file
ownership; a writer is never its own sole reviewer.

## 4. Reconcile and fix

1. Wait for every planned role. Save each reply and merge them:
   `python3 <skill>/scripts/merge_findings.py <replies> --head <sha> --repo-root <tree>`.
   It groups the same issue reported by several roles, keeps every source, and
   flags incomplete or stale-head roles. Do not average away disagreement.
2. Verify each group against code and repository rules. Unsupported assumptions
   are not confirmed problems; missing context is not disproof.
3. Fix supported in-scope issues, including valid nits, with meaningful
   regression tests (not tests that restate a copy change).
4. For a real product decision or out-of-scope remedy, ask the user a precise
   question with the trigger, consequence and options; do not publish a
   supposedly clean PR until it is resolved. Record the decision for the PR body.
5. A disproved finding needs evidence. Confidence scores, timeouts, reviewer
   silence or a lowered severity are not disproof.
6. After fixes: verify, commit, rebuild the packet with
   `--previous-head <old head> --findings <dispositions file>`, and send it to
   the affected roles plus Maya's incremental fix check. Reuse earlier evidence
   only where the inspected code is unchanged, and say so.
7. If rounds stop making progress, isolate the disagreement and ask the user.

## 5. Pass gate

`passed` requires: every required role complete for the final head, every
finding dispositioned with evidence, no open actionable finding or decision, and
the applicable checks passing. An infrastructure failure is reported with
evidence and fixed or explicitly accepted by the user; accepting it never turns
an unrun reviewer into a completed one, and never allows attestation.

Immediately before push, fetch the target again, re-read head/tree/tip/merge-base
and worktree status, refresh any review the change affects, and confirm the
pushed remote head equals the reviewed head. This applies to every later push
for review fixes too. A previous attestation label proves nothing by itself.

## Review record

Keep it beside the packet: repository, SHAs, criteria, tier, role plan,
self-check result, each role's definition/model/effort, call ID, observed model,
tokens and duration, findings with dispositions, verification commands and
results, decisions asked of the user, and the final gate result.
