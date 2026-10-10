# Local review protocol

## 1. Freeze what will be pushed

Finish implementation and applicable verification, then make task-only local
commits. **Local commits are allowed before review; remote pushes are not.**
Never `git add .` in a shared checkout; preserve unrelated work rather than
stashing or committing it blindly. Fetch the target branch (fetching is not
pushing) and build the packet:

```sh
python3 <skill>/scripts/review_packet.py --repo <task tree> --base origin/main --fetch \
  --runtime claude|codex|opencode|dsh --roles themis,pandora,proteus,odysseus \
  --criteria <file or text> --stale '<old value>' --stale '<old id>'
```

It refuses a dirty tree, records head/tree/target-tip/merge-base SHAs, exports
the **entire** PR diff from the merge base (never just `HEAD~1`), lists the
applicable `AGENTS.md`/`CLAUDE.md`/`REVIEW.md`, writes `self-check.md` and one
prompt per role under `<git-path>/pr-shepherd-review/<head12>/`, outside tracked
source. It also adds Icarus, Hephaestus or Palamedes when the change has a signal for them
([routing](roles.md#routing)) and lists the matches under "Specialists required
by signals" in `self-check.md`; keep them in the plan. Without Python, do the
same steps by hand.

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
Describe each call with the role's `label` from `manifest.json`: name, what it
checks, model and effort ("Pandora · Bugs review · Opus medium"; merged calls join
them, e.g. "Themis+Mnemosyne · Guidelines and comments review · Sonnet medium"), not
the PR title. The agent type shown beside it is the shared definition. Odysseus gets no other findings or author claims. Evidence agents do get the
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
3. Fix supported in-scope issues with meaningful regression tests (not tests
   that restate a copy change). Rounds 1 and 2 fix every supported finding,
   nits included; from round 3 the stop rule (8) applies.
4. For a real product decision or out-of-scope remedy, ask the user a precise
   question with the trigger, consequence and options; do not publish a
   supposedly clean PR until it is resolved. Record the decision for the PR body.
5. A disproved finding needs evidence. Confidence scores, timeouts, reviewer
   silence or a lowered severity are not disproof.
6. After fixes: verify, commit, rebuild the packet with
   `--previous-head <old head> --findings <dispositions file>`, and send it to
   the affected roles plus Pandora's incremental fix check. Reuse earlier evidence
   only where the inspected code is unchanged, and say so.
7. **A substantial fix is new code, not a fix.** A fix is substantial when it
   adds a function, file, state, cache, retry, lock or parser, changes control
   flow in more than one place, or touches more than one source file; count
   the fixes of all rounds together, so splitting does not avoid it. When in
   doubt, it is substantial. Then an incremental check is not enough: rebuild
   the packet without `--previous-head` and run Odysseus fresh on the whole diff,
   plus every specialist the new code signals, as well as Pandora.
8. **Stop rule.** A *round* is one dispatch-and-merge cycle, counted per PR from
   the first packet; a fresh pass under 7 and the post-PR phase continue the
   same count. A finding is *blocking* when its trigger leads to wrong
   behaviour, a security or routing bypass, data loss or a regression, judged
   by the consequence, whatever severity was assigned. From round 3, fix only
   blocking findings; record the rest (precision, wording, cosmetic) with a
   one-line reason in the review record and the PR body as known limits, and
   start no new round for them. Calling a reviewer's critical or important
   finding non-blocking needs source evidence and is listed for the user in
   the final report; if disputed, ask the user or the originating reviewer. If
   each round finds new blocking issues in code the previous round wrote,
   treat it as a design problem: stop patching, simplify or narrow the change,
   and tell the user.
9. If rounds stop making progress, isolate the disagreement and ask the user.

## 5. Pass gate

`passed` requires: every required role complete for the final head, every
finding dispositioned with evidence (fixed, disproved, or recorded as a
non-blocking known limit under the stop rule), no open blocking finding or
decision, a fresh full-diff pass for every substantial fix (7), and the
applicable checks passing. An infrastructure failure is reported with
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
results, decisions asked of the user, known limits with their reasons, and
the final gate result.

Known legacy persona names are accepted as CLI aliases in `--roles` and
`--specialist-signal`; generated packets use Greek identities. Security requests
for Artemis promote to Athena when the detector finds a sensitive signal.
`--roles athena` explicitly requests the stronger row. Renaming does not change
models, efforts or the detector.
