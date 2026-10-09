# Review roles

Each role is a reviewer persona with one responsibility. The names are short
handles for the plan, progress and PR summary; they say nothing about the model
(see the model matrices). Running these roles locally is not a claim that any
remote review pipeline ran.

Every prompt names the role's scope **and what to leave to others**. Overlap is
the main waste in a local review: the same stale sentence reported by five
roles costs five reviews. A role may still report something outside its scope
when it is critical, marked `out_of_scope: true`.

| Role | Name | Owns | Leaves to others |
| --- | --- | --- | --- |
| Guidelines | Themis | Explicit AGENTS/CLAUDE/REVIEW rules; quotes the exact rule broken, including required doc updates. | Whether prose matches code (Mnemosyne); code bugs (Pandora). |
| Bugs | Pandora | Concrete incorrect behavior: boundaries, races, cleanup, error paths, reachable null states. | Doc wording, style, architecture opinions. |
| Architecture | Daedalus | Callers, compatibility, service/data contracts, side effects, rollout/rollback, failure propagation. | Line-level bugs (Pandora); types (Proteus); doc wording. |
| Types | Proteus | Runtime data versus assumed types, validation, narrowing, casts at external boundaries; not compiler output. | Behavior bugs that are not type-shaped. |
| Comments and intent | Mnemosyne | Stale or false comments, JSDoc, test names and docs versus the code at this head. | Rule compliance (Themis); code bugs. |
| Independent review | Odysseus | A fresh full-diff review; sees no other findings or author claims before returning. | Nothing: deliberately overlapping second opinion. |
| Security | Artemis | Authorization, untrusted input, injection, secrets, trust boundaries, data exposure. | Non-security bugs. |
| Security | Athena | Authentication, authorization, secrets, trust boundaries and the high-risk signals below. | Non-security bugs. |
| Performance | Icarus | Hot paths, queries, network calls, allocations, bounded work, resource limits. | Correctness bugs. |
| Code quality | Hephaestus | Introduced maintainability problems with a concrete consequence or rule. | Speculative refactors; style a linter owns. |
| Language | Palamedes | Language-specific correctness and conventions for the language actually changed. | Cross-language architecture. |
| Self-reflection | Psyche | Challenges findings for false positives and actual impact. | New findings. |
| Debate | Harmonia | Resolves conflicting findings/fixes from source; exposes genuine user decisions. | New findings. |
| Confidence | Metis | Whether evidence supports each finding; a number never erases a concrete hypothesis. | New findings. |
| Verification | Theseus | Reproduces or traces a finding and verifies the proposed fix. | New findings. |
| Fact check | Aletheia | Real signatures, schemas, imports, callers and official docs, not assumed APIs. | New findings. |
| Reachability | Ariadne | Guards and state transitions behind null/undefined/initialization claims. | New findings. |
| Incremental fix check | Pandora | Confirms each fix and inspects its consumers for regressions. | Re-reviewing unchanged areas. |

Optional companion roles: Calliope (PR summary), Prometheus (change guide), Cadmus
(translations), Cassandra (E2E relevance), Peitho (comment replies). The coordinator may
do them; they never count as independent code review.

## Routing

- **Basic:** small, isolated implementation with no contract or trust-boundary
  change. Pandora and Odysseus as separate agents, plus applicable specialists.
- **Standard:** ordinary code changes. Themis, Pandora, Proteus and Odysseus. Without
  written repository guidance, Daedalus replaces Themis.
- **Deep:** shared API/schema changes, cross-service behavior, security,
  concurrency, lifecycle changes, broad refactors, substantial agent/workflow
  instructions, or model/cost policy. Themis, Pandora, Daedalus, Proteus, Mnemosyne and Odysseus.

**Docs-and-rules merge.** When most of the diff is documentation, policy or
instructions, run Themis and Mnemosyne as one call ("Themis+Mnemosyne") that owns both
columns. It still counts as both roles.

Artemis is required when trust, auth, secret, input or permission boundaries
change. **Whether Artemis or Athena runs is decided by signals in the diff, not by
judgement** (`review_packet.py` detects them and records the matches): Athena
(the stronger security row) when changed paths or added lines touch
authentication (login, session, JWT, OAuth, access/refresh/bearer tokens,
cookies, passwords, MFA), authorization (permissions, RBAC/ACL, role checks,
row-level security), trust boundaries (webhooks, HMAC/signature checks, CORS,
CSRF, gateways), secrets and crypto (secrets, API/private keys, encryption,
password hashing, KMS), infra permissions (workflow `permissions:`/`secrets.`,
IAM, Dockerfile `USER`, security groups), production commerce APIs (the
commercetools SDK or API), payments (Stripe, Adyen, Klarna, PayPal, payment
intents/methods/providers, refunds), personal data where it is stored or
queried (email, phone, address, birth date in migrations, schemas, models or
SQL/ORM writes), or when security-relevant changes span two or more top-level
packages. Repository instructions can add their own production API clients as
`--security-signal NAME=REGEX`. Otherwise routine Artemis (input validation,
sanitization or injection checks in one component, dependency bumps, sensitive
logging). When unsure, use Athena. The coordinator may raise routine to Athena
with a stated reason, never lower a detected Athena, and names the decision and
its matches in the plan and the PR body.

Icarus is required for hot paths/resource changes; Hephaestus for structural complexity;
Palamedes for language-specific behavior outside the others' expertise. Do not run
specialists only to fill a matrix. Downstream review settings and the optional
attestation label never lower this profile. Pandora and Odysseus are always distinct
first-pass calls.

**When findings exist,** run one evidence agent covering Theseus, Aletheia and Metis
(and Ariadne for null/initialization findings); its output names each check
separately. Deep reviews also run Psyche, and Harmonia when findings conflict. If the
coordinator does this evidence work itself instead, the review is still valid
for publishing but is **not** a passing review for attestation; say so in the
PR. The author alone never independently verifies a disputed fix.

## What every role does

Inspect relevant unchanged callers, tests and contracts. Report only introduced
issues anchored to changed behavior, each with a concrete trigger, consequence,
source location and suggested fix. Missing source means inspect it or report
`needs_context`; it is neither a proven bug nor a disproof. Before returning no
findings, try a realistic counterexample to each changed guard, validation rule,
return or side effect.
