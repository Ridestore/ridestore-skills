#!/bin/sh
# Validate the Codex and Claude Code catalogs, every plugin in them and the
# OpenCode skill indexes. Runs `claude plugin validate` when the CLI is present.
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

python3 "$root/scripts/validate_catalogs.py"
python3 "$root/scripts/build_opencode_index.py" --check
for dir in plugins/*/; do
  matrix="$dir/skills/${dir#plugins/}"
  matrix="${matrix%/}/scripts/check_matrix.py"
  [ -f "$matrix" ] && python3 "$matrix" --plugin-manifest "$dir.claude-plugin/plugin.json"
done

if command -v claude >/dev/null 2>&1; then
  claude plugin validate .
  for dir in plugins/*/; do
    [ -d "$dir" ] || continue
    claude plugin validate "$dir"
  done
else
  echo "claude CLI not found: skipped claude plugin validate"
fi
