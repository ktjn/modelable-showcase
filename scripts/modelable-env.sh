#!/usr/bin/env bash
# Source this file (do not execute it) to make the project-local `modelable`
# CLI resolve on PATH regardless of shell profile state:
#
#   source scripts/modelable-env.sh
#
# `uv tool install` places executables in uv's per-user tool bin directory,
# which is not guaranteed to already be on PATH in a fresh CI shell. This
# only exports PATH for the current shell/script - it never writes to
# ~/.bashrc, ~/.profile, or any other global machine file.

if command -v uv >/dev/null 2>&1; then
  _modelable_tool_bin="$(uv tool dir --bin 2>/dev/null || true)"
fi
: "${_modelable_tool_bin:=$HOME/.local/bin}"

case ":${PATH}:" in
  *":${_modelable_tool_bin}:"*) ;;
  *) export PATH="${_modelable_tool_bin}:${PATH}" ;;
esac

# Put a project-local pinned protoc (scripts/install-protoc.sh, .protoc-version)
# on PATH the same way, so `modelable compile --descriptor-set` and the
# protobuf/gRPC codegen probes can find it without a global install.
_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
_protoc_version="$(tr -d ' \t\n\r' < "${_script_dir}/../.protoc-version" 2>/dev/null || true)"
if [ -n "${_protoc_version}" ] && [ -x "${_script_dir}/../tools/protoc-${_protoc_version}/bin/protoc" ]; then
  _protoc_bin="$(cd "${_script_dir}/../tools/protoc-${_protoc_version}/bin" && pwd)"
  case ":${PATH}:" in
    *":${_protoc_bin}:"*) ;;
    *) export PATH="${_protoc_bin}:${PATH}" ;;
  esac
fi

unset _modelable_tool_bin
unset _script_dir
unset _protoc_version
unset _protoc_bin
