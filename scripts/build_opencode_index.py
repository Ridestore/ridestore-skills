"""Write plugins/<plugin>/skills/index.json for OpenCode remote skill discovery.

OpenCode has no plugin marketplace; it reads `"skills": ["<url>/"]` from
opencode.json, fetches `<url>/index.json` ({"skills": [{name, version, files}]})
and downloads `<url>/<skill>/<file>`. The skill version is the plugin version, so
OpenCode refreshes its cache on every release.

    python3 scripts/build_opencode_index.py          # rewrite the index files
    python3 scripts/build_opencode_index.py --check  # fail if any is stale (CI)
"""

import json
import os
import sys

SKIP = {".DS_Store", "__pycache__"}


def skill_files(skill_dir):
    files = []
    for root, dirs, names in os.walk(skill_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(names):
            if name in SKIP or name.endswith(".pyc"):
                continue
            files.append(os.path.relpath(os.path.join(root, name), skill_dir).replace(os.sep, "/"))
    return files


def build(plugin_dir):
    version = json.load(open(os.path.join(plugin_dir, ".claude-plugin", "plugin.json"))).get("version")
    skills_dir = os.path.join(plugin_dir, "skills")
    skills = []
    for name in sorted(os.listdir(skills_dir)):
        path = os.path.join(skills_dir, name)
        if os.path.isfile(os.path.join(path, "SKILL.md")):
            skills.append({"name": name, "version": version, "files": skill_files(path)})
    return json.dumps({"skills": skills}, indent=2) + "\n"


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for plugin in sorted(os.listdir("plugins")):
        plugin_dir = os.path.join("plugins", plugin)
        if not os.path.isdir(os.path.join(plugin_dir, "skills")):
            continue
        target = os.path.join(plugin_dir, "skills", "index.json")
        text = build(plugin_dir)
        current = open(target).read() if os.path.isfile(target) else None
        if current == text:
            continue
        if check:
            stale.append(target)
        else:
            with open(target, "w") as fh:
                fh.write(text)
            print(f"wrote {target}")
    if stale:
        print("stale OpenCode index (run python3 scripts/build_opencode_index.py):\n  " + "\n  ".join(stale))
        return 1
    if check:
        print("opencode indexes ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
