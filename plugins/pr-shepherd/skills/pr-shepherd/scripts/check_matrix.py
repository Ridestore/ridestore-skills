#!/usr/bin/env python3
"""Check the model matrices against the reviewer definitions and their age.

- every definition named in references/claude-models.md exists in agents/ and
  pins the same model and effort as the table;
- every agents/*-reviewer*.md definition is used by the table (and, with
  --plugin-manifest, registered in the plugin's `agents` list);
- every dsh tool named in references/dsh-models.md is a row of
  agents/dsh/cordis.patch.yml with the same model and effort, DeepSeek only,
  read-only tools and depth 1;
- every matrix carries a `Last verified: YYYY-MM-DD` line; one older than
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


def dsh_tools(path):
    """toolName -> settings of each pr-shepherd row in the dsh patch fragment."""
    tools = {}
    for block in re.split(r"^\s*- id: ", open(path, encoding="utf-8").read(), flags=re.M)[1:]:
        get = lambda key: (re.search(r"^\s*" + key + r":\s*(.+)$", block, re.M) or [None, None])[1]
        tools[get("toolName")] = {"model": get("model"), "effort": get("reasoningEffort"),
                                  "llm": re.findall(r"^\s+provider:\s*(\S+)", block, re.M),
                                  "allow": get("allow"), "depth": get("maxDepth")}
    return tools


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

    oc_used = set()
    for cells in table_rows(os.path.join(refs, "opencode-models.md")):
        if len(cells) < 4 or not re.fullmatch(r"[a-z0-9-]+", cells[3]):
            continue
        name, model, effort = cells[3], cells[1].strip("`"), cells[2]
        oc_used.add(name)
        path = os.path.join(args.skill_dir, "agents", "opencode", f"{name}.md")
        if not os.path.isfile(path):
            errors.append(f"opencode {cells[0]}: agent {name} not found in agents/opencode/")
            continue
        fm = frontmatter(path)
        if fm.get("model") != model:
            errors.append(f"opencode {cells[0]}: table pins {model}, {name} pins {fm.get('model')}")
        if fm.get("reasoningEffort", "provider default") != effort:
            errors.append(f"opencode {cells[0]}: table says effort {effort}, {name} sets {fm.get('reasoningEffort', 'none')}")
        if fm.get("mode") != "subagent":
            errors.append(f"{path}: mode must be subagent")
    for path in glob.glob(os.path.join(args.skill_dir, "agents", "opencode", "*.md")):
        if os.path.basename(path)[:-3] not in oc_used:
            errors.append(f"agents/opencode/{os.path.basename(path)} is not used by references/opencode-models.md")

    patch = os.path.join(args.skill_dir, "agents", "dsh", "cordis.patch.yml")
    tools = dsh_tools(patch) if os.path.isfile(patch) else {}
    dsh_used = set()
    for cells in table_rows(os.path.join(refs, "dsh-models.md")):
        if len(cells) < 4 or not re.fullmatch(r"[a-z0-9_]+", cells[3]):
            continue
        name, model, effort = cells[3], cells[1].strip("`"), cells[2]
        dsh_used.add(name)
        tool = tools.get(name)
        if not tool:
            errors.append(f"dsh {cells[0]}: tool {name} not found in agents/dsh/cordis.patch.yml")
            continue
        if (tool["model"], tool["effort"]) != (model, effort):
            errors.append(f"dsh {cells[0]}: table pins {model}/{effort}, {name} pins {tool['model']}/{tool['effort']}")
    for name, tool in sorted(tools.items()):
        if name not in dsh_used:
            errors.append(f"agents/dsh/cordis.patch.yml: {name} is not used by references/dsh-models.md")
        if tool["llm"] != ["spawn", "deepseek-official"] or not str(tool["model"]).startswith("deepseek-"):
            errors.append(f"agents/dsh/cordis.patch.yml: {name} must use the spawn provider and a deepseek-official model")
        if tool["allow"] != "[read, grep, glob]" or tool["depth"] != "1":
            errors.append(f"agents/dsh/cordis.patch.yml: {name} must allow only [read, grep, glob] at maxDepth 1")

    defined = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(args.skill_dir, "agents", "*-reviewer*.md"))}
    for name in sorted(defined - used):
        errors.append(f"agents/{name}.md is not used by references/claude-models.md")
    if args.plugin_manifest:
        listed = {os.path.basename(p)[:-3] for p in json.load(open(args.plugin_manifest)).get("agents", [])}
        for name in sorted(defined - listed):
            errors.append(f"{args.plugin_manifest}: agents list misses {name}")

    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    for matrix in ("claude-models.md", "codex-models.md", "opencode-models.md", "dsh-models.md"):
        text = open(os.path.join(refs, matrix), encoding="utf-8").read()
        date = last_verified(os.path.join(refs, matrix))
        if not date and re.search(r"Last verified:\s*not yet", text):
            warnings.append(f"{matrix}: never verified at runtime; run one review and record it")
        elif not date:
            errors.append(f"{matrix}: no 'Last verified: YYYY-MM-DD' (or 'not yet') line")
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
