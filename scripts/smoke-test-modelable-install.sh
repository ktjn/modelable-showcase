#!/usr/bin/env bash
# CI-ready smoke test for IMPLEMENTATION_PLAN.md Task 1.2: proves the
# installed Modelable CLI is real and produces valid JSON capabilities
# output, not just that install-modelable.sh exited 0.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/install-modelable.sh"

# shellcheck source=./modelable-env.sh
source "${SCRIPT_DIR}/modelable-env.sh"

out="$(mktemp)"
trap 'rm -f "${out}"' EXIT

modelable capabilities --format json > "${out}"
python3 -m json.tool "${out}" >/dev/null

count="$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "${out}")"
if [ "${count}" -lt 1 ]; then
  echo "smoke-test-modelable-install.sh: capabilities JSON parsed but reported zero capabilities" >&2
  exit 1
fi

echo "smoke-test-modelable-install.sh: OK - $(modelable --version), ${count} capabilities reported"
