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

unset _modelable_tool_bin
