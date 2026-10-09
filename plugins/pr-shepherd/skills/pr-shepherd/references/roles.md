# Review roles

Each role is a reviewer persona with one responsibility. The names are short
handles that keep the plan, progress and PR summary readable; they say nothing
about which model runs a role (see the model matrices). Running these roles
locally is not a claim that any remote review pipeline ran.

| Role | Name | Responsibility |
| --- | --- | --- |
| Guidelines | Finn | Explicit applicable AGENTS/CLAUDE/REVIEW rules; quote the exact violated rule. |
| Bugs | Maya | Concrete incorrect behavior, boundaries, races, cleanup, error paths and reachable null states. |
| Architecture | Theo | Callers, compatibility, service/data contracts, side effects, concurrency and failure propagation. |
| Types | Nora | Runtime data versus assumed types, validation, narrowing and external boundaries; not duplicate compiler output. |
| Comments and intent | Jasper | Changed code versus documented intent, stale comments and misleading API documentation. |
| Independent review | Felix | A fresh review of the complete diff; do not show other findings until its independent pass returns. |
| Security | Remy | Authorization, untrusted input, injection, secrets, trust boundaries and data exposure. |
| Performance | Ruby | Hot paths, queries, network calls, allocations, bounded work and resource limits. |
| Code quality | Oscar | Introduced maintainability problems with concrete consequences or explicit rules; avoid speculative refactors. |
| Language | Iris | Language-specific correctness and conventions for the language actually changed. |
| Self-reflection | Zoe | Challenge findings for false positives, introduced behavior and actual impact. |
| Debate | Cleo | Resolve conflicting findings/fixes using source evidence; expose genuine user decisions. |
| Confidence | Milo | State whether evidence supports the finding; never use a confidence number alone to erase a concrete unresolved hypothesis. |
| Verification | Vera | Reproduce or trace a finding and independently verify the proposed fix. |
| Fact check | Otis | Inspect real signatures, schemas, imports, callers and official docs rather than assumed APIs. |
| Reachability | Luna | Trace guards and state transitions for null, undefined and initialization claims. |
| Incremental fix check | Maya | Confirm each fix and inspect its consumers for regressions. |

Optional companion roles: Ada (PR summary), Eli (change guide), Sofia
(translations), Hugo (E2E relevance), and Max (comment replies). The coordinator
may perform these support duties. They do not count as independent code review.
Translation execution and live E2E need their own applicable tools and evidence.

## Routing

- **Basic:** small, isolated implementation with no contract or trust-boundary
  change. Run Maya and Felix as separate native agents, plus applicable specialists.
  The coordinator still checks
  repository rules and verifies findings.
- **Standard:** ordinary code changes. Run Finn, Maya, Nora and Felix. If the repo
  has no written guidance, replace Finn with Theo. Add specialists according
  to the actual diff.
- **Deep:** shared API/schema changes, cross-service behavior, security,
  concurrency, lifecycle changes, broad refactors or substantial agent/workflow
  instructions. Run Finn, Maya, Theo, Nora and Jasper, plus Felix as an
  independent agent. Add relevant specialists.

The local quality profile deliberately retains an independent second opinion
even for Basic changes. Downstream review settings and the
optional attestation label never lower this local profile. Use the runtime's
versioned matrix; spend on relevant depth and independent evidence, not repeated
identical reviews. A specialist can combine evidence duties where stated below,
but Maya and Felix must be distinct first-pass calls.

Remy is required when trust, auth, secret, input or permission boundaries
change; Ruby for hot paths/resource changes; Oscar for structural complexity;
Iris for language-specific behavior outside the other reviewers' expertise.
Do not run unrelated specialists only to fill a matrix.

When findings exist, run Vera with Otis and Milo responsibilities; run Luna
for null/initialization findings. Deep reviews also run Zoe, and Cleo when
findings conflict or two or more findings need reconciliation. These roles
may share a single evidence subagent when its output separately names the
checks it performed. A reviewer may self-reflect, but the author alone cannot
provide the independent verification of a disputed fix.

Every review must inspect relevant unchanged callers, tests and contracts.
Report only introduced issues anchored to the changed behavior. Include a
concrete trigger, consequence, source location and suggested fix. Missing
source means inspect it or report `needs_context`; it is neither a proven bug
nor proof that a finding is false. Before returning no findings, try a realistic
counterexample to each changed guard, validation rule, return or side effect.
