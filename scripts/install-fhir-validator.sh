#!/usr/bin/env bash
# Install a pinned, checksum-verified copy of the official HL7 FHIR Validator
# CLI into a project-local tools/ directory - no global machine mutation
# (mirrors scripts/install-protoc.sh's approach). Optional: only needed by
# tests/integration/test_generated_artifacts.py's HL7 FHIR Validator smoke
# check (IMPLEMENTATION_PLAN.md Task 15.4, Phase 15). Not part of
# `make bootstrap`; that test skips cleanly when the jar isn't present.
#
# Requires Java (already a project dependency - the C#/Java probes and this
# showcase's own generated java-core use it).
#
# The version is pinned in .fhir-validator-version and the exact release
# asset's SHA-256 is pinned below, verified after download - "do not
# download arbitrary binaries at runtime without checksum/version pinning"
# (IMPLEMENTATION_PLAN.md Task 15.4).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="$(tr -d ' \t\n\r' < "${REPO_ROOT}/.fhir-validator-version")"
TOOLS_DIR="${REPO_ROOT}/tools"
JAR_PATH="${TOOLS_DIR}/validator_cli.jar"
URL="https://github.com/hapifhir/org.hl7.fhir.core/releases/download/${VERSION}/validator_cli.jar"
# Pinned SHA-256 of the validator_cli.jar asset published under the
# ${VERSION} GitHub release tag above - re-verify and update this alongside
# any version bump.
EXPECTED_SHA256="a3addadfa18dfa23146a0a243b6ede68eaad92157a5407738c468bb3d7e4ccd6"

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    echo "install-fhir-validator.sh: neither sha256sum nor shasum is available" >&2
    exit 1
  fi
}

if [ -f "${JAR_PATH}" ]; then
  actual="$(sha256_of "${JAR_PATH}")"
  if [ "${actual}" = "${EXPECTED_SHA256}" ]; then
    echo "install-fhir-validator.sh: validator_cli.jar ${VERSION} already installed and verified at ${JAR_PATH}" >&2
    exit 0
  fi
  echo "install-fhir-validator.sh: ${JAR_PATH} exists but does not match the pinned checksum - re-downloading" >&2
fi

mkdir -p "${TOOLS_DIR}"
TMP_JAR="$(mktemp)"
echo "install-fhir-validator.sh: downloading ${URL}" >&2
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 -o "${TMP_JAR}" "${URL}"
elif command -v wget >/dev/null 2>&1; then
  wget -O "${TMP_JAR}" "${URL}"
else
  echo "install-fhir-validator.sh: neither curl nor wget is available" >&2
  rm -f "${TMP_JAR}"
  exit 1
fi

actual="$(sha256_of "${TMP_JAR}")"
if [ "${actual}" != "${EXPECTED_SHA256}" ]; then
  echo "install-fhir-validator.sh: checksum mismatch for ${URL}" >&2
  echo "  expected: ${EXPECTED_SHA256}" >&2
  echo "  actual:   ${actual}" >&2
  rm -f "${TMP_JAR}"
  exit 1
fi

mv "${TMP_JAR}" "${JAR_PATH}"
echo "install-fhir-validator.sh: installed and verified validator_cli.jar ${VERSION} at ${JAR_PATH}" >&2
