# Local-review attestation (optional)

Some teams run an automated PR reviewer that can trust a recorded local review,
for example by switching to cheaper models when one is present. This protocol
publishes that evidence. It is **off by default**: use it only when repository
or workspace instructions name the label to apply (a common choice is
`autoreviewed-locally`). The label is a per-PR hint, not an approval. Writing
the evidence does not prove that any service reads or honors it.

## Publish a completed review

After the required local role review passes, include exactly one marker in
the author-written part of the PR body, outside sections managed by review
automation, in this format (replace placeholders with full 40-character SHAs):

```html
<!-- local-review:v1 {"head":"<reviewed-head-sha>","base":"<target-branch-tip-sha>","status":"passed"} -->
```

If repository instructions name a different marker prefix (for example an
existing `<org>-local-review:v1` that their automation already parses), use that
prefix instead and keep the same JSON fields.

- `head`: the exact local commit reviewed, which must match the pushed PR head.
- `base`: the exact tip SHA of the PR's target branch fetched for this review.
  This is **not** the merge-base SHA. Record both values separately in local
  evidence; reviewers still inspect the full diff from the merge base.
- `status`: the literal `passed`, only after the complete review pass gate.

Keep a human-readable review summary beside it: actual roles/models, checks
and any limitations. Never write `passed` after a skip, timeout, incomplete
review or unresolved blocking finding (known limits recorded under the stop
rule are listed in the summary). Never copy a marker from another PR or repeat
its syntax in the author's prose/code examples. A quotation inside a block
managed by review automation is not another author attestation; do not edit
the service's blocks to supply evidence.

Before creation, inspect/create the label as described in SKILL.md. Include
the marker in the initial body and, where the GitHub tool supports it, include
the label in the same PR-create operation. Verify the resulting live head,
base, body and label. If the label must be added separately, the first review
may already have selected its ordinary policy; do not cancel/duplicate a
running review just to claim savings.

## Freshness and updates

On new code, remove/invalidate the old attestation; review and validate the
resulting local head before pushing. Replace the existing marker rather than
appending another. Refresh evidence only when it actually covers the new
head and target branch state. An old marker, missing label, malformed JSON,
ambiguous duplicate markers or a changed head/base must leave downstream
automation on its ordinary policy. A new target-branch tip is not permission to
blindly rewrite the base SHA: inspect the changed baseline and reconsider
applicable evidence.

If possible, update an existing PR's marker for the reviewed new head before
pushing that head. It then mismatches the old head safely, and the push event
can see matching evidence. Recheck the live target after the push. Otherwise
accept an ordinary-policy run during the timing gap; never grant a stale
attestation to save money.

## What it must never do

The label and body are author-supplied provenance, not signed proof that agents
ran. They must never satisfy approval, merge, branch-protection, CI or review
coverage requirements by themselves, and they never lower this skill's own
local review profile. Do not claim a measured token or cost reduction without
actual telemetry.
