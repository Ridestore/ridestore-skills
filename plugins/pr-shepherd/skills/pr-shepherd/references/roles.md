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
| Guidelines | Finn | Explicit AGENTS/CLAUDE/REVIEW rules; quotes the exact rule broken, including required doc updates. | Whether prose matches code (Jasper); code bugs (Maya). |
| Bugs | Maya | Concrete incorrect behavior: boundaries, races, cleanup, error paths, reachable null states. | Doc wording, style, architecture opinions. |
| Architecture | Theo | Callers, compatibility, service/data contracts, side effects, rollout/rollback, failure propagation. | Line-level bugs (Maya); types (Nora); doc wording. |
| Types | Nora | Runtime data versus assumed types, validation, narrowing, casts at external boundaries; not compiler output. | Behavior bugs that are not type-shaped. |
| Comments and intent | Jasper | Stale or false comments, JSDoc, test names and docs versus the code at this head. | Rule compliance (Finn); code bugs. |
| Independent review | Felix | A fresh full-diff review; sees no other findings or author claims before returning. | Nothing: deliberately overlapping second opinion. |
| Security | Remy | Authorization, untrusted input, injection, secrets, trust boundaries, data exposure. | Non-security bugs. |
| Performance | Ruby | Hot paths, queries, network calls, allocations, bounded work, resource limits. | Correctness bugs. |
| Code quality | Oscar | Introduced maintainability problems with a concrete consequence or rule. | Speculative refactors; style a linter owns. |
| Language | Iris | Language-specific correctness and conventions for the language actually changed. | Cross-language architecture. |
| Self-reflection | Zoe | Challenges findings for false positives and actual impact. | New findings. |
| Debate | Cleo | Resolves conflicting findings/fixes from source; exposes genuine user decisions. | New findings. |
| Confidence | Milo | Whether evidence supports each finding; a number never erases a concrete hypothesis. | New findings. |
| Verification | Vera | Reproduces or traces a finding and verifies the proposed fix. | New findings. |
| Fact check | Otis | Real signatures, schemas, imports, callers and official docs, not assumed APIs. | New findings. |
| Reachability | Luna | Guards and state transitions behind null/undefined/initialization claims. | New findings. |
| Incremental fix check | Maya | Confirms each fix and inspects its consumers for regressions. | Re-reviewing unchanged areas. |

Optional companion roles: Ada (PR summary), Eli (change guide), Sofia
(translations), Hugo (E2E relevance), Max (comment replies). The coordinator may
do them; they never count as independent code review.

## Routing

- **Basic:** small, isolated implementation with no contract or trust-boundary
  change. Maya and Felix as separate agents, plus applicable specialists.
- **Standard:** ordinary code changes. Finn, Maya, Nora and Felix. Without
  written repository guidance, Theo replaces Finn.
- **Deep:** shared API/schema changes, cross-service behavior, security,
  concurrency, lifecycle changes, broad refactors, substantial agent/workflow
  instructions, or model/cost policy. Finn, Maya, Theo, Nora, Jasper and Felix.

**Docs-and-rules merge.** When most of the diff is documentation, policy or
instructions, run Finn and Jasper as one call ("Finn+Jasper") that owns both
columns. It still counts as both roles.

Remy is required when trust, auth, secret, input or permission boundaries
change. **Which model Remy uses is decided by signals in the diff, not by
judgement** (`review_packet.py` detects them and records the matches): Remy+
(the stronger security row) when changed paths or added lines touch
authentication (login, session, JWT, OAuth, access/refresh/bearer tokens,
cookies, passwords, MFA), authorization (permissions, RBAC/ACL, role checks,
row-level security), trust boundaries (webhooks, HMAC/signature checks, CORS,
CSRF, gateways), secrets and crypto (secrets, API/private keys, encryption,
password hashing, KMS), infra permissions (workflow `permissions:`/`secrets.`,
IAM, Dockerfile `USER`, security groups), production commerce APIs (the
commercetools SDK or API), payments (Stripe, Adyen, Klarna, PayPal, payment
intents/methods/providers, refunds), personal data where it is stored or queried
(email, phone, address, birth date in migrations, schemas, models or SQL/ORM
writes), a `.gitattributes` line that changes how files diff, a file git shows
as binary that is not an image, font, archive or other asset (its lines are
hidden), or when security-relevant changes span two or more top-level packages.
Repository instructions can add their own production API clients as
`--security-signal NAME=REGEX` (recorded as `repo: NAME`; it adds, never
replaces). Otherwise routine Remy (input validation, sanitization or injection
checks in one component, dependency bumps, sensitive logging). When unsure, use
Remy+. The coordinator may raise routine to Remy+ with a stated reason, never
lower a detected Remy+, and names the decision and its matches in the plan and
the PR body.

**Ruby, Oscar and Iris are also routed by signals, not by judgement.**
`review_packet.py` adds each one to the plan when the change under review (the
whole PR, or for a fix check the changes since the reviewed head) has a signal
for it in changed code or config, and records the matches in the manifest and
`self-check.md`. Docs, tests, fixtures, lockfiles, generated or vendored output,
snapshots and translation or data files are ignored.

- **Ruby (performance):** SQL and ORM calls, network calls, a query, call or
  `await` inside a loop body, request/webhook/cron/queue handlers, pools,
  semaphores, locks, concurrency and rate limits, `Promise.all` and batch work,
  caches and TTLs, timeouts, retries and polling, blocking sync calls,
  module-level `Map`/`Set`/dict collections, pagination, streams and buffered
  bodies, migrations and indexes, frontend render and loading work (`useMemo`,
  `memo`, dynamic imports, observers, scroll listeners) and runtime/build limits
  (PM2, Kubernetes, Wrangler, bundler config). CI workflows, container files,
  styles and package manifests are left to Iris, and deleting a file routes no
  specialist.
- **Oscar (code quality):** in source files, 150+ added lines in one file, a new
  file of 300+ lines, 400+ added lines in total, 10+ files, five or more added
  lines six levels deep in the file's own indent unit (eight in markup), and
  escape hatches and dynamic code: `eval`/`exec` calls, `new Function`, `Proxy`,
  `setattr`/`__getattr__`/`metaclass`, monkeypatching, a TypeScript `any` type,
  Python `global`/`nonlocal`, `@ts-ignore`/`@ts-nocheck`, lint or type-check
  suppressions and FIXME/HACK.
- **Iris (language):** shell scripts, SQL and Prisma, Dockerfiles and compose,
  CI workflows, infrastructure code, build and package config (not release
  metadata such as `version`), styles, regular expressions, dates, time zones
  and money arithmetic, encoding and Unicode, async runtime semantics, advanced
  type-system constructs, module-system edges (`import.meta`, `createRequire`,
  `exports` maps), signal handling and resource disposal, and added lines in two
  or more programming languages (JavaScript and TypeScript count as one).

Repository instructions can add their own as `--specialist-signal
ROLE:NAME=REGEX` (for example a hot internal client for Ruby); they are recorded
as `repo: NAME` and add to the built-in signals, never replace one. The
coordinator may add a specialist with a stated reason, never drop a signalled
one, and names the decision and its matches in the plan and the PR body. Do not
run specialists without a signal or reason only to fill a matrix. Downstream
review settings and the optional attestation label never lower this profile.
Maya and Felix are always distinct first-pass calls.

**When findings exist,** run one evidence agent covering Vera, Otis and Milo
(and Luna for null/initialization findings); its output names each check
separately. Deep reviews also run Zoe, and Cleo when findings conflict. If the
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
