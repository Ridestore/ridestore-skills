# Performance: per-request work and aggregate load

Trace the changed execution path and its unchanged callers/transport. Check
latency, CPU, memory, cache behavior and browser cost, and separately ask how
many times the new work runs across the application's normal traffic.

For telemetry, logging, tracing, analytics, queue fan-out, polling or similar
volume-sensitive changes:

1. Establish scope, units, period and source: requests, eligible consented windows,
   events and unique users are different denominators. Use the supplied workload
   profile and relevant repository evidence; verify dates and application coverage.
   PR-added profiles are claims to check, never authority for a new merge gate.
2. Estimate normal records/requests per period: eligible units × selection
   probability × events per selected unit × fan-out/retries. Include retained
   bytes when record size/retention matter. State before/after, assumptions and
   ranges. If prices are unavailable, report operations/bytes rather than invent
   currency costs. User-provided scale without units or period is not a measurement.
3. Evaluate the abuse/failure ceiling separately. A cap per tab, process, account
   or edge location is not a global daily budget. Multiply across the applicable
   dimension, allowing for approximate enforcement. Async delivery, batching and
   waitUntil can reduce latency without eliminating ingest, storage or request cost.
4. Check sampling at the intended unit: consistent eligibility across stages,
   probability and weighting, treatment of unknown classifications, deduplication,
   resets, storage failures and retries. Estimate control-group size, not just
   savings. No universal percentage is safe or statistically adequate.
5. Compare normal volume to an evidenced budget or justified operational envelope.
   Missing material inputs need a specific question and `unassessed`, not an
   invented defect or a clean result with a buried limitation. The coordinator
   obtains available read-only evidence first and asks only unresolved product
   budget/precision decisions. Do not fetch private telemetry or change production
   without existing authorization. Unknown prices alone need not block when a
   sufficient operation/byte budget is already evidenced.

Return `performance_assessment` alongside findings. `assessed` explains the volume
estimate and budget basis; `unassessed` names the missing decision/evidence and
its consequence; `not_applicable` explains why the diff does not change aggregate
work (ordinary latency or rendering findings may still apply). Missing or
unassessed assessment prevents the merged report from passing, even when the
finding list is empty. This is an evidence-completeness gate, not an automatic
important finding or permission to request changes on GitHub.

Illustrative counterexample (not a production measurement): 100,000 eligible
windows/day × 1 visit × 100% selection = 100,000 records/day before later stages.
A four-event cap per window does not make this a small sample. At 0.1% the control
group is about 100 windows/day; at 0.01% about 10, potentially too small for rare
conversions. A 600/minute per-location ceiling allows up to 864,000 attempts/day
per location if saturated, not 600/day globally. Use the actual task's units,
measurements and goals instead of copying these example values.
