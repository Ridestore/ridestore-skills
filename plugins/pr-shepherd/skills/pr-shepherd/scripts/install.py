#!/usr/bin/env python3
"""Link one trusted package into Codex/Claude (and optionally OpenCode and dsh); refuse unmanaged collisions."""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
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
# Files removed from the package; the installer deletes its own leftovers.
RETIRED_OPENCODE_AGENTS = ("pr-shepherd-astra.md", "pr-shepherd-sol-medium.md", "pr-shepherd-luna-xhigh.md")
RETIRED_CLAUDE_AGENTS = ("opus-reviewer.md", "opus-reviewer-xhigh.md", "sonnet-reviewer-xhigh.md")
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
# Our rows, matched however a copy outside the block is written: an id in any key
# position or quoting, or a tool name (dsh requires distinct tool names).
DSH_ROW = re.compile(r"""\bid:\s*["']?pr-shepherd-|\btoolName:\s*["']?pr_shepherd_""")
# A top-level `- id: pr-shepherd-…` item outside the block overrides fields of our
# row (dsh patches rows by id), which is supported.
DSH_OVERRIDE = re.compile(r"""-\s+id:\s*["']?pr-shepherd-[a-z0-9-]+["']?[ \t]*(#[^\n]*)?\r?\n""")


def ours_retired(dest, agents_dir, copies_here):
    """A retired file this installer created: a link into the package's agent
    directory (even if dangling), or, where it writes copies, a copy whose second
    line is our marker."""
    if dest.is_symlink():
        return Path(os.path.join(dest.parent, os.readlink(dest))).parent.resolve() == agents_dir
    if copies_here and dest.is_file():
        lines = dest.read_text().splitlines()
        return len(lines) > 1 and lines[0] == "---" and lines[1].startswith(MANAGED_COPY + " (")
    return False


def read_exact(path):
    with open(path, newline="") as fh:  # keep CRLF and other bytes outside the block as they are
        return fh.read()


def dsh_outside_problem(outside):
    """Why text outside the managed block makes appending unsafe, or None. The file
    must be a YAML block list starting at column 0, with no copies of our rows."""
    items, lines = [], [l for l in outside.splitlines(True) if l.strip() and not l.lstrip().startswith("#")]
    if lines and not lines[0].startswith("-"):
        return "not a YAML block list at column 0"
    for line in lines:
        if not line[0].isspace():
            if not line.startswith("-"):
                return "not a YAML block list at column 0"
            items.append(line)
        else:
            items[-1] += line
    for item in items:
        if DSH_ROW.search(item) and not DSH_OVERRIDE.match(item):
            return "pr-shepherd rows already exist outside the managed block"
    return None


def dsh_patch_record(dest, fragment):
    """Plan the managed block in dsh's home patch. Text outside the markers is never
    changed; a file we cannot append to safely is a collision."""
    record = {"path": str(dest), "expected_target": "managed block from agents/dsh/cordis.patch.yml"}
    if dest.is_symlink() or (dest.exists() and not dest.is_file()):
        record.update(status="collision", error="not a regular file", _text=None)
        return record
    current = read_exact(dest) if dest.is_file() else ""
    nl = "\r\n" if "\r\n" in current else "\n"
    block = nl.join([DSH_BEGIN, fragment.rstrip(), DSH_END]) + nl
    begin, end = current.find(DSH_BEGIN), current.find(DSH_END)
    if current.count(DSH_BEGIN) == 1 and current.count(DSH_END) == 1 and begin < end:
        tail = current.index("\n", end) + 1 if "\n" in current[end:] else len(current)
        outside, new = current[:begin] + current[tail:], current[:begin] + block + current[tail:]
    elif DSH_BEGIN in current or DSH_END in current:
        outside, new = None, None
    else:
        sep = nl if current and not current.endswith("\n") else ""
        outside, new = current, current + sep + block
    problem = "unpaired or duplicate pr-shepherd markers" if outside is None else dsh_outside_problem(outside)
    if problem:
        record.update(status="collision", error=problem, _text=None)
    else:
        record.update(status="patched" if new == current else "outdated" if begin != -1 else "missing",
                      _text=new, _current=current)
    return record


def replace_file(dest, text, expected):
    """Write next to dest, then rename over it, so an interrupted install never
    leaves the user's file truncated. Refuses if the file changed since planning."""
    if (dest.exists() or dest.is_symlink()) and (dest.is_symlink() or read_exact(dest) != expected):
        raise ValueError(f"{dest} changed while installing; nothing written, run again")
    if not dest.exists() and expected:
        raise ValueError(f"{dest} disappeared while installing; nothing written, run again")
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=dest.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if dest.exists():
            shutil.copymode(dest, tmp)
        else:
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, dest)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


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
    # (root, source dir its links point into, retired names, whether managed copies live there)
    retired = [(args.claude_agents_root, source / "agents", RETIRED_CLAUDE_AGENTS, False)]
    if args.opencode_root:
        retired.append((args.opencode_root, source / "agents" / "opencode", RETIRED_OPENCODE_AGENTS, True))
    for root, agents_dir, names, copies_here in retired:
        for name in names:
            dest = root.expanduser().absolute() / name
            if ours_retired(dest, agents_dir, copies_here):
                records.append({"path": str(dest), "expected_target": "retired agent, removed", "status": "stale",
                                "_agents_dir": str(agents_dir), "_copies": copies_here})
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
        code = 1 if any(r["status"] in ("missing", "outdated", "stale") for r in records) else 0
    else:
        code = 0
        for r in records:
            if r["status"] == "stale":
                r["action"] = "remove"
                if args.install:
                    dest = Path(r["path"])
                    if not ours_retired(dest, Path(r["_agents_dir"]), r["_copies"]):
                        raise ValueError(f"{dest} changed while installing; nothing removed, run again")
                    dest.unlink()
                    r["status"] = "removed"
                continue
            if r["status"] == "outdated" or (r["status"] == "missing" and r.get("expected_target", "").startswith("managed block")):
                r["action"] = "patch"
                if args.install:
                    dest = Path(r["path"])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    replace_file(dest, r["_text"], r["_current"])
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
        r.pop("_current", None)
        r.pop("_agents_dir", None)
        r.pop("_copies", None)
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(2)
