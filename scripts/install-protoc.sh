#!/usr/bin/env bash
# Install a pinned protoc into a project-local tools/ directory - no global
# machine mutation, and CI can reproduce the exact same install (mirrors
# scripts/install-modelable.sh's approach).
#
# protoc is only needed by the protobuf/gRPC codegen probes (IMPLEMENTATION_PLAN.md
# Task 7.5) and by `modelable compile --descriptor-set`, which invokes protoc on
# PATH. The version is pinned in .protoc-version. The bundled include/ directory
# (google/protobuf well-known types) travels with the binary, so a consumer can
# pass `-I <protoc-dir>/include` to resolve `google/protobuf/timestamp.proto`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION="$(tr -d ' \t\n\r' < "${REPO_ROOT}/.protoc-version")"
TOOLS_DIR="${REPO_ROOT}/tools"
PROTOC_DIR="${TOOLS_DIR}/protoc-${VERSION}"

if [ -x "${PROTOC_DIR}/bin/protoc" ]; then
  echo "install-protoc.sh: protoc ${VERSION} already installed at ${PROTOC_DIR}" >&2
  exit 0
fi

# Map uname output to the protobuf release archive suffix.
OS="$(uname -s)"
ARCH="$(uname -m)"
case "${OS}-${ARCH}" in
  Linux-x86_64)   SUFFIX="linux-x86_64" ;;
  Linux-aarch64)  SUFFIX="linux-aarch_64" ;;
  Darwin-x86_64)  SUFFIX="osx-x86_64" ;;
  Darwin-arm64)   SUFFIX="osx-aarch_64" ;;
  *)
    echo "install-protoc.sh: unsupported platform ${OS}-${ARCH}" >&2
    echo "  Windows: install-protoc.sh targets POSIX shells; on Windows place" >&2
    echo "  protoc-${VERSION}-win64.zip's bin/ on PATH (tools/protoc-${VERSION}/bin) and" >&2
    echo "  pass -I tools/protoc-${VERSION}/include for the google well-known types." >&2
    exit 1
    ;;
esac

URL="https://github.com/protocolbuffers/protobuf/releases/download/v${VERSION}/protoc-${VERSION}-${SUFFIX}.zip"
mkdir -p "${TOOLS_DIR}"
TMP_ZIP="$(mktemp)"
echo "install-protoc.sh: downloading ${URL}" >&2
if command -v curl >/dev/null 2>&1; then
  curl -fL --retry 3 -o "${TMP_ZIP}" "${URL}"
elif command -v wget >/dev/null 2>&1; then
  wget -O "${TMP_ZIP}" "${URL}"
else
  echo "install-protoc.sh: neither curl nor wget is available" >&2
  rm -f "${TMP_ZIP}"
  exit 1
fi

mkdir -p "${PROTOC_DIR}"
if command -v unzip >/dev/null 2>&1; then
  unzip -q -o "${TMP_ZIP}" -d "${PROTOC_DIR}"
else
  python3 -c "import shutil, sys; shutil.unpack_archive(sys.argv[1], sys.argv[2], 'zip')" "${TMP_ZIP}" "${PROTOC_DIR}"
fi
rm -f "${TMP_ZIP}"

"${PROTOC_DIR}/bin/protoc" --version >/dev/null 2>&1
echo "install-protoc.sh: installed protoc ${VERSION} at ${PROTOC_DIR}" >&2
echo "  Add ${PROTOC_DIR}/bin to PATH (scripts/modelable-env.sh does this) so" >&2
echo "  'modelable compile --descriptor-set' and the codegen probes can find it." >&2