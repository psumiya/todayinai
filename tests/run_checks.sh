#!/usr/bin/env bash
# Offline checks: archive builds clean, a bad edition is rejected, a good one publishes. Runs in a temp copy.
set -euo pipefail
python -m newsletter.build --strict
tmp=$(mktemp -d); cp -r . "$tmp"; cd "$tmp"
if python -m newsletter.run --fixture tests/fixture_bad --date 2099-01-01 >/dev/null; then echo "FAIL: bad edition accepted"; exit 1; fi
sed -i 's/"date": "2026-10-22"/"date": "2099-01-01"/' tests/fixture/response.json
python -m newsletter.run --fixture tests/fixture --date 2099-01-01 >/dev/null
test -f data/editions/2099-01-01.json
echo "PASS"
