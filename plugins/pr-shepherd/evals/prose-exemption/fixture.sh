#!/bin/bash
set -e
git init -q -b main
git config user.email eval@example.com; git config user.name eval
printf 'Demo helper.\n\nRun `make tset` to run tests.\n' > README.md
printf 'all:\n\ttrue\n' > Makefile
git add -A && git commit -qm base
