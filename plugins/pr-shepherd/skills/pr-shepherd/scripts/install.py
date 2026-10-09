#!/usr/bin/env python3
"""Link one trusted package into Codex/Claude (and optionally OpenCode and dsh); refuse unmanaged collisions."""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path


REQUIRED = ("SKILL.md", "agents/openai.yaml", "scripts/install.py",
            "scripts/review_packet.py", "scripts/merge_findings.py", "scripts/check_matrix.py",
            "references/claude-models.md", "references/codex-models.md",
            "references/local-review.md", "references/roles.md",
            "references/progress.md", "references/workspaces.md",
            "references/attestation.md", "references/post-pr.md",
            "references/maintenance.md", "references/dsh-models.md",
            "agents/dsh/cordis.patch.yml")


# OpenCode fallback when neither OpenAI (GPT) nor Anthropic (Claude) is connected:
# DeepSeek first, then GLM; one model for every role.
OPENCODE_PROFILES = {"deepseek": "deepseek/deepseek-flash", "glm": "zhipuai/glm-5.3"}
MANAGED_COPY = "# pr-shepherd-managed-copy"
PROVIDER_ENV = {"openai": ["OPENAI_API_KEY"], "anthropic": ["ANTHROPIC_API_KEY"],
                "deepseek": ["DEEPSEEK_API_KEY"], "glm": ["ZHIPU_API_KEY", "ZHIPUAI_API_KEY", "ZAI_API_KEY", "GLM_API_KEY"]}
PROVIDER_IDS = {"openai": r'"openai"', "anthropic": r'"anthropic"', "deepseek": r'"deepseek"',
                "glm": r'"(?:zhipuai|zai|zai-coding-plan|glm)[a-z0-9-]*"'}


def opencode_providers(home=None, env=None):
    """Providers OpenCode can use: API-key variables, saved logins (auth.json) and
    provider sections in opencode.json(c). Reads only; never prints secrets."""
    home, env = home or Path.home(), env if env is not None else os.environ
    found = {name for name, keys in PROVIDER_ENV.items() if any(env.get(k) for k in keys)}
    blob = "\n".join(p.read_text(errors="ignore") for p in (
        home / ".local/share/opencode/auth.json", home / ".config/opencode/opencode.json",
        home / ".config/opencode/opencode.jsonc") if p.is_file()).lower()
    found |= {name for name, pattern in PROVIDER_IDS.items() if re.search(pattern, blob)}
    return found


def opencode_profile(found):
    """GPT or Claude connected: the mixed default. Otherwise DeepSeek, then GLM."""
    if found & {"openai", "anthropic"}:
        return "default"
    return "deepseek" if "deepseek" in found else "glm" if "glm" in found else "default"


def opencode_copy(agent, profile):
    """Agent file with the profile's model and no OpenAI-only reasoningEffort, marked as managed."""
    text = re.sub(r"^model: .*$", f"model: {OPENCODE_PROFILES[profile]}", agent.read_text(), count=1, flags=re.M)
    text = re.sub(r"^reasoningEffort: .*\n", "", text, flags=re.M)
    return text.replace("---\n", f"---\n{MANAGED_COPY} ({profile})\n", 1)


DSH_BEGIN = "# >>> pr-shepherd (managed by install.py) >>>"
DSH_END = "# <<< pr-shepherd <<<"


def dsh_patch_record(dest, fragment):
    """Plan the managed block in dsh's home patch (a YAML block list). Text outside
    the markers is never changed; a file we cannot append to safely is a collision."""
    block = f"{DSH_BEGIN}\n{fragment.rstrip()}\n{DSH_END}\n"
    current = dest.read_text() if dest.is_file() else ""
    record = {"path": str(dest), "expected_target": "managed block from agents/dsh/cordis.patch.yml"}
    begin, end = current.find(DSH_BEGIN + "\n"), current.find(DSH_END + "\n")
    if dest.is_symlink() or (dest.exists() and not dest.is_file()):
        status, new = "collision", None
    elif begin != -1 and end > begin and current.count(DSH_BEGIN) == 1:
        outside = current[:begin] + current[end + len(DSH_END) + 1:]
        new = current[:begin] + block + current[end + len(DSH_END) + 1:]
        status = "collision" if re.search(r"^\s*- id: pr-shepherd-", outside, re.M) else "patched" if new == current else "outdated"
    elif DSH_BEGIN in current or DSH_END in current or re.search(r"^\s*- id: pr-shepherd-", current, re.M):
        status, new = "collision", None
    else:
        top = [l for l in current.splitlines() if l.strip() and not l.lstrip().startswith("#") and not l[0].isspace()]
        status = "missing" if all(l.startswith("- ") or l == "-" for l in top) else "collision"
        new = current + ("\n" if current and not current.endswith("\n") else "") + block
    if status == "collision":
        record["error"] = "not a YAML block list, or pr-shepherd rows exist outside the managed block"
    record["status"], record["_text"] = status, new
    return record


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
    parser.add_argument("--opencode-root", type=Path, help="also install agents/opencode/*.md here (e.g. ~/.config/opencode/agents)")
    parser.add_argument("--opencode-profile", choices=["auto", "default", "deepseek", "glm"], default="auto",
                        help="auto: GPT/Claude connected -> default mix; else DeepSeek; else GLM")
    parser.add_argument("--dsh-home", type=Path, help="also install for DeepSeek Harness: link the skill into "
                        "<dsh-home>/skills and add the reviewer tools to <dsh-home>/cordis.patch.yml (e.g. ~/.dsh)")
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
    providers = opencode_providers() if args.opencode_root else set()
    profile = (opencode_profile(providers) if args.opencode_profile == "auto" else args.opencode_profile) if args.opencode_root else None
    copies = []
    if args.opencode_root:
        for agent in sorted((source / "agents" / "opencode").glob("*.md")):
            if profile == "default":
                targets.append((args.opencode_root, agent.name, agent))
            else:
                copies.append((args.opencode_root.expanduser().absolute() / agent.name, agent, opencode_copy(agent, profile)))
    records = []
    if args.dsh_home:
        dsh_home = args.dsh_home.expanduser().absolute()
        targets.append((dsh_home / "skills", "pr-shepherd", source))
        records.append(dsh_patch_record(dsh_home / "cordis.patch.yml",
                                        (source / "agents" / "dsh" / "cordis.patch.yml").read_text()))
    for dest, agent, text in copies:
        exists = dest.exists() or dest.is_symlink()
        ours = (dest.is_symlink() and dest.resolve() == agent) or (dest.is_file() and not dest.is_symlink() and MANAGED_COPY in dest.read_text())
        current = dest.is_file() and not dest.is_symlink() and dest.read_text() == text
        status = "copied" if current else "collision" if exists and not ours else "missing"
        records.append({"path": str(dest), "expected_target": f"copy of {agent} ({profile})", "status": status, "_text": text})
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
              "opencode": {"providers": sorted(providers), "profile": profile} if args.opencode_root else None,
              "dsh": {"home": str(args.dsh_home.expanduser().absolute()), "binary": shutil.which("dsh")} if args.dsh_home else None,
              "mode": "check" if args.check else "install" if args.install else "dry-run",
              "targets": records}
    if any(r["status"] == "collision" for r in records):
        report["error"] = "Unmanaged destination collision; nothing overwritten"
        code = 2
    elif args.check:
        code = 1 if any(r["status"] in ("missing", "outdated") for r in records) else 0
    else:
        code = 0
        for r in records:
            if r["status"] == "outdated" or (r["status"] == "missing" and r.get("expected_target", "").startswith("managed block")):
                r["action"] = "patch"
                if args.install:
                    dest = Path(r["path"])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(r["_text"])
                    r["status"] = "patched"
                continue
            if r["status"] != "missing":
                continue
            if "_text" in r:
                r["action"] = "copy"
                if args.install:
                    dest = Path(r["path"])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if dest.is_symlink():
                        dest.unlink()
                    dest.write_text(r["_text"])
                    r["status"] = "copied"
                continue
            r["action"] = "link"
            if args.install:
                dest = Path(r["path"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(r["expected_target"], target_is_directory=dest.name == "pr-shepherd")
                r["status"] = "linked"
                r["resolved_version"] = version
    for r in records:
        r.pop("_text", None)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)
