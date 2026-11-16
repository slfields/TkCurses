#!/bin/sh
# Regenerate every lock file in this directory from pyproject.toml and the
# .in files beside it. Run from the repository root after changing a
# dependency, or to take newer versions:
#
#     sh requirements/lock.sh
#
# Each lock is universal - one file for Python 3.10 to 3.14 and every
# platform - and carries a hash for every file, so CI installs with
# --require-hashes and gets exactly what was locked or nothing. Needs uv
# (https://docs.astral.sh/uv/). Security review TkCurses-tcbj.8.
set -eu
cd "$(dirname "$0")/.."
lock() {
    out=$1
    shift
    uv pip compile --quiet --universal --python-version 3.10 \
        --generate-hashes --no-header --output-file "requirements/$out" "$@"
}
lock test.txt pyproject.toml --extra test
lock dev.txt pyproject.toml --extra dev
lock docs.txt pyproject.toml --extra docs --extra test requirements/release.in
lock release.txt requirements/release.in
lock security.txt requirements/security.in
