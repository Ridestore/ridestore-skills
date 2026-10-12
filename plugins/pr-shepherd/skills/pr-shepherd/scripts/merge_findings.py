#!/usr/bin/env python3
"""Merge reviewer results into one deduplicated findings list and a pass-gate summary.

Each input is a reviewer's reply (a file holding the JSON result, possibly with
text around it). Findings in the same file within --window lines are grouped as
one issue, keeping every reporting role and its evidence. Writes findings.md and
findings.json next to the first input (or into --out) and prints the summary.

Exit code: 0 when every role completed for --head and no group is blocking or
unassessed; 1 otherwise. Evidence and applicability still need coordinator review.

  merge_findings.py results/*.json --manifest <packet>/manifest.json --head <sha>
"""

import argparse
import json
import os
import sys
from review_packet import LEGACY_ROLES

SEVERITY = ["critical", "important", "minor", "low", "nit"]


def canonical_role(value):
    if not isinstance(value, str):
        return ""
    value = value.strip().lower()
    return "icarus" if value == "performance" else LEGACY_ROLES.get(value, value)


def extract_json(text):
    """First JSON object in a reply, ignoring prose or code fences around it."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object found")


def rank(severity):
    s = (severity or "minor").lower()
    return SEVERITY.index(s) if s in SEVERITY else SEVERITY.index("minor")


def norm_path(path, roots):
    path = path or "?"
    for root in roots:
        if root and path.startswith(root.rstrip("/") + "/"):
            return path[len(root.rstrip("/")) + 1:]
    return path


def group(findings, window):
    groups = []
    for f in sorted(findings, key=lambda f: (f["file"], f.get("line") or 0)):
        line = f.get("line") or 0
        for g in groups:
            if g["file"] == f["file"] and abs(g["line"] - line) <= window:
                g["items"].append(f)
                break
        else:
            groups.append({"file": f["file"], "line": line, "items": [f]})
    for n, g in enumerate(sorted(groups, key=lambda g: (min(rank(i.get("severity")) for i in g["items"]), g["file"])), 1):
        g["id"] = f"G{n}"
        g["severity"] = SEVERITY[min(rank(i.get("severity")) for i in g["items"])]
        g["roles"] = sorted({i["role"] for i in g["items"]})
    return sorted(groups, key=lambda g: int(g["id"][1:]))


def impact_classification(finding):
    """Structural triage only; a source-grounded coordinator decides semantic truth."""
    if finding.get("disposition") == "needs_context":
        return "unassessed"
    basis = finding.get("blocking_basis")
    present = lambda key: isinstance(finding.get(key), str) and bool(finding[key].strip())
    if basis == "concrete-impact" and all(present(key) for key in ("trigger", "impact", "evidence")):
        return "blocking"
    if basis == "merge-requirement" and all(present(key) for key in ("rule_quote", "rule_source", "evidence")):
        return "blocking"
    if basis == "none" and present("evidence"):
        return "advisory"
    # Legacy and malformed results need adjudication, not a fabricated downgrade.
    return "unassessed"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--manifest", required=True, help="frozen packet manifest; required roles cannot be inferred from supplied results")
    ap.add_argument("--head", help="frozen head SHA every result must name")
    ap.add_argument("--repo-root", action="append", default=[], help="absolute prefix to strip from paths")
    ap.add_argument("--window", type=int, default=5, help="lines apart that still count as one issue")
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
        required_roles = manifest["roles"]
        expected_head = manifest["head"]
        if not isinstance(required_roles, dict) or not required_roles or not isinstance(expected_head, str) or not expected_head:
            raise ValueError("manifest requires nonempty roles and head")
        expected_roles = {canonical_role(role) for role in required_roles}
        if "" in expected_roles or len(expected_roles) != len(required_roles):
            raise ValueError("invalid or duplicate canonical roles in manifest")
        if args.head and args.head != expected_head:
            raise ValueError("--head differs from frozen manifest")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"invalid review manifest: {exc}")

    roles, findings, problems = [], [], []
    seen = set()
    for path in args.results:
        try:
            result = extract_json(open(path, encoding="utf-8").read())
        except (OSError, ValueError) as exc:
            problems.append(f"{path}: unreadable result ({exc})")
            continue
        role = canonical_role(result.get("role", os.path.splitext(os.path.basename(path))[0]))
        if not role or role not in expected_roles:
            problems.append(f"{path}: unexpected role {role!r}; must match the frozen manifest")
        if role in seen:
            problems.append(f"{role}: duplicate result")
        seen.add(role)
        status = result.get("status", "incomplete")
        stale = result.get("head") != expected_head
        roles.append({"role": role, "status": status, "head": result.get("head"), "stale": stale,
                      "findings": len(result.get("findings") or []), "limitations": result.get("limitations") or []})
        if status != "complete":
            problems.append(f"{role}: status {status}")
        if stale:
            problems.append(f"{role}: reviewed {result.get('head')}, not {expected_head}")
        if role == "icarus":
            assessment = result.get("performance_assessment")
            roles[-1]["performance_assessment"] = assessment
            valid = isinstance(assessment, dict)
            state = assessment.get("status") if valid else None
            required = ("reason", "volume_estimate", "budget_basis") if state == "assessed" else ("reason",)
            if state not in ("assessed", "not_applicable") or not all(
                    isinstance(assessment.get(k), str) and assessment[k].strip() for k in required):
                problems.append(f"{role}: aggregate performance assessment missing, unassessed or invalid; resolve material workload/budget questions")
        for f in result.get("findings") or []:
            findings.append({**f, "role": role, "file": norm_path(f.get("file"), args.repo_root)})

    problems.extend(f"{role}: required result missing" for role in sorted(expected_roles - seen))

    groups = group(findings, args.window)
    for g in groups:
        classes = {impact_classification(item) for item in g["items"]}
        g["classification"] = "unassessed" if "unassessed" in classes or len(classes) > 1 else next(iter(classes))
    blocking = [g for g in groups if g["classification"] == "blocking"]
    unassessed = [g for g in groups if g["classification"] == "unassessed"]
    advisory = [g for g in groups if g["classification"] == "advisory"]
    problems.extend(f"{g['id']}: impact evidence missing or conflicting; coordinator adjudication required" for g in unassessed)
    summary = {"roles": roles, "problems": problems, "groups": len(groups), "findings": len(findings),
               "by_severity": {s: sum(1 for g in groups if g["severity"] == s) for s in SEVERITY},
               "complete": not problems, "blocking_groups": [g["id"] for g in blocking],
               "advisory_groups": [g["id"] for g in advisory], "unassessed_groups": [g["id"] for g in unassessed]}

    out = args.out or os.path.dirname(os.path.abspath(args.results[0]))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "findings.json"), "w") as fh:
        json.dump({"summary": summary, "groups": groups}, fh, indent=2)
    with open(os.path.join(out, "findings.md"), "w") as fh:
        fh.write("# Review findings\n\n")
        fh.write("| Role | Status | Findings |\n| --- | --- | --- |\n")
        fh.writelines(f"| {r['role']} | {r['status']}{' (stale head)' if r['stale'] else ''} | {r['findings']} |\n" for r in roles)
        if problems:
            fh.write("\n**Review incomplete:** " + "; ".join(problems) + "\n")
        for role in roles:
            if isinstance(role.get("performance_assessment"), dict):
                fh.write("\n## Performance assessment\n\n")
                for key, value in role["performance_assessment"].items():
                    fh.write(f"- {key}: {value}\n")
        fh.write("\n| Group | Severity | Roles | Location | Issue | Disposition |\n| --- | --- | --- | --- | --- | --- |\n")
        for g in groups:
            first = g["items"][0]
            issue = (first.get("title") or first.get("impact") or first.get("trigger") or "").replace("\n", " ")[:160]
            fh.write(f"| {g['id']} | {g['severity']} | {', '.join(g['roles'])} | {g['file']}:{g['line']} | {issue} | |\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["complete"] and not blocking else 1


if __name__ == "__main__":
    sys.exit(main())
