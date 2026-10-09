#!/usr/bin/env python3
"""Link one trusted package into Codex/Claude; refuse unmanaged collisions."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


REQUIRED = ("SKILL.md", "agents/openai.yaml", "scripts/install.py",
            "scripts/review_packet.py", "scripts/merge_findings.py", "scripts/check_matrix.py",
            "references/claude-models.md", "references/codex-models.md",
            "references/local-review.md", "references/roles.md",
            "references/progress.md", "references/workspaces.md",
            "references/attestation.md", "references/post-pr.md",
            "references/maintenance.md")


def validate_package(source):
    missing = [name for name in REQUIRED if not (source / name).is_file()]
    if missing:
        raise ValueError("Incomplete source package; missing: " + ", ".join(missing))
    for doc in source.rglob("*.md"):
        for link in re.findall(r"\]\(([^)\s]+)\)", doc.read_text()):
            if ":" in link or link.startswith("#"):
                continue
            target = (doc.parent / link.split("#", 1)[0]).resolve()
            if not target.is_relative_to(source) or not target.is_file():
                raise ValueError(f"Missing or non-package local reference in {doc}: {link}")


def field(text, name):
    match = re.search(r"^\s*" + re.escape(name) + r":\s*[\"']?([^\n\"']+)", text, re.M)
    if not match:
        raise ValueError(f"Missing {name} in package metadata")
    return match.group(1).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("check", "dry-run", "install"):
        modes.add_argument("--" + mode, action="store_true")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--codex-root", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--claude-root", type=Path, default=Path.home() / ".claude/skills")
    parser.add_argument("--claude-agents-root", type=Path, default=Path.home() / ".claude/agents")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    validate_package(source)
    skill = (source / "SKILL.md").read_text()
    if field(skill, "name") != "pr-shepherd":
        raise ValueError("Source is not the pr-shepherd package")
    version = field(skill, "version")
    targets = [(args.codex_root, "pr-shepherd", source),
               (args.claude_root, "pr-shepherd", source)]
    models = {}
    agents = sorted(p.stem for p in (source / "agents").glob("*-reviewer*.md"))
    if not agents:
        raise ValueError("Source package has no reviewer definitions in agents/")
    for name in agents:
        agent = source / "agents" / (name + ".md")
        text = agent.read_text()
        if field(text, "name") != name:
            raise ValueError(f"Agent definition name mismatch: {agent}")
        models[name] = field(text, "model")
        targets.append((args.claude_agents_root, name + ".md", agent))
    records = []
    for root, name, expected in targets:
        dest = root.expanduser().absolute() / name
        exists = dest.exists() or dest.is_symlink()
        managed = dest.is_symlink() and dest.resolve() == expected
        status = "linked" if managed else "collision" if exists else "missing"
        record = {"path": str(dest), "expected_target": str(expected), "status": status}
        if exists:
            record["resolved_target"] = str(dest.resolve())
        if managed:
            metadata = dest / "SKILL.md" if expected.is_dir() else dest
            record["sha256"] = hashlib.sha256(metadata.read_bytes()).hexdigest()
            record["resolved_version"] = version
        records.append(record)
    report = {"source": str(source), "version": version, "models": models,
              "mode": "check" if args.check else "install" if args.install else "dry-run",
              "targets": records}
    if any(r["status"] == "collision" for r in records):
        report["error"] = "Unmanaged destination collision; nothing overwritten"
        code = 2
    elif args.check:
        code = 1 if any(r["status"] == "missing" for r in records) else 0
    else:
        code = 0
        for r in records:
            if r["status"] != "missing":
                continue
            r["action"] = "link"
            if args.install:
                dest = Path(r["path"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(r["expected_target"], target_is_directory=dest.name == "pr-shepherd")
                r["status"] = "linked"
                r["resolved_version"] = version
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)
