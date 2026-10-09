#!/usr/bin/env python3
"""Check the model matrices against the reviewer definitions and their age.

- every definition named in references/claude-models.md exists in agents/ and
  pins the same model and effort as the table;
- every agents/*-reviewer*.md definition is used by the table (and, with
  --plugin-manifest, registered in the plugin's `agents` list);
- both matrices carry a `Last verified: YYYY-MM-DD` line; one older than
  --max-age-days is reported (an error with --strict).

Exit 1 on any mismatch, or on stale verification with --strict.
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def table_rows(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("|"):
            if not re.match(r"^\|\s*:?-", line):  # skip the separator row
                rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif rows:
            break
    return rows[1:]


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M)) if m else {}


def last_verified(path):
    m = re.search(r"Last verified:\s*(\d{4}-\d{2}-\d{2})", open(path, encoding="utf-8").read())
    return datetime.date.fromisoformat(m.group(1)) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skill-dir", default=SKILL_DIR)
    ap.add_argument("--plugin-manifest", help="Claude plugin.json whose `agents` list must register every definition")
    ap.add_argument("--max-age-days", type=int, default=60)
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for tests")
    ap.add_argument("--strict", action="store_true", help="fail when a matrix verification is too old")
    args = ap.parse_args(argv)

    refs = os.path.join(args.skill_dir, "references")
    errors, warnings = [], []
    used = set()
    for cells in table_rows(os.path.join(refs, "claude-models.md")):
        if len(cells) < 4 or not re.fullmatch(r"[a-z0-9-]+", cells[3]):
            continue  # coordinator / companion rows
        name, model, effort = cells[3], cells[1].strip("`"), cells[2]
        used.add(name)
        path = os.path.join(args.skill_dir, "agents", f"{name}.md")
        if not os.path.isfile(path):
            errors.append(f"{cells[0]}: definition {name} not found in agents/")
            continue
        fm = frontmatter(path)
        if fm.get("name") != name:
            errors.append(f"{path}: name {fm.get('name')!r} != {name!r}")
        if fm.get("model") != model:
            errors.append(f"{cells[0]}: table pins {model}, {name} pins {fm.get('model')}")
        if fm.get("effort") != effort:
            errors.append(f"{cells[0]}: table says effort {effort}, {name} pins {fm.get('effort')}")

    defined = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(args.skill_dir, "agents", "*-reviewer*.md"))}
    for name in sorted(defined - used):
        errors.append(f"agents/{name}.md is not used by references/claude-models.md")
    if args.plugin_manifest:
        listed = {os.path.basename(p)[:-3] for p in json.load(open(args.plugin_manifest)).get("agents", [])}
        for name in sorted(defined - listed):
            errors.append(f"{args.plugin_manifest}: agents list misses {name}")

    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    for matrix in ("claude-models.md", "codex-models.md"):
        date = last_verified(os.path.join(refs, matrix))
        if not date:
            errors.append(f"{matrix}: no 'Last verified: YYYY-MM-DD' line")
        elif (today - date).days > args.max_age_days:
            (errors if args.strict else warnings).append(
                f"{matrix}: last verified {date} ({(today - date).days} days ago); re-run a native review and update it")

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    if not errors:
        print(f"matrix ok: {len(used)} definitions match their pins")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
