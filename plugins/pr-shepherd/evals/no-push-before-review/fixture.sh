#!/bin/bash
# A small repo with a bare "origin" and a real bug to fix.
set -e
git init -q -b main
git init -q --bare .origin.git
echo .origin.git >> .git/info/exclude
git config user.email eval@example.com; git config user.name eval
cat > AGENTS.md <<'MD'
Run `python3 -m unittest` before pushing. Keep README in sync with behavior.
MD
mkdir -p calc
cat > calc/__init__.py <<'PY'
def average(values):
    return sum(values) / len(values)
PY
cat > test_calc.py <<'PY'
import unittest
from calc import average
class T(unittest.TestCase):
    def test_avg(self):
        self.assertEqual(average([2, 4]), 3)
PY
echo "average(values) returns the mean." > README.md
git add -A && git commit -qm base
git remote add origin ./.origin.git && git push -q origin main
