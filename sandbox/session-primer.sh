#!/bin/bash
# SessionStart hook: tell the agent it is inside a Minimal sandbox and how to
# reach for `min` instead of a system package manager.
#
# Keep this short. It is injected into every session's context. Anything that
# is not needed on every turn belongs in the minimal-sandbox skill instead.
set -euo pipefail

# Stay silent outside a Minimal sandbox, where the shim is not installed.
[ -x /usr/bin/min ] || exit 0

read -r -d '' context << 'EOF' || true
You are running inside a Minimal sandbox (a session or a task sandbox). The
host filesystem is not mounted, and system package managers (apt, apk, dnf,
brew) are unavailable. Do not attempt to install software with them, and do
not install into the system with pip or npm.

The `min` here is the in-sandbox helper, not the host session CLI that shares
its name: host commands (min session, min init, min bug, mip ...) do not
exist in here. Install tools with the helper instead:

  min search <term>            find a package by name
  min add <pkg>...             install into this sandbox
  min add --build <pkg>...     install and record as a build dependency
  min add --runtime <pkg>...   install and record as a runtime dependency
  min run <task>               run a minimal.toml task

In a session, bare `min add` also records the package in the project's
[session] packages list; in a task sandbox it is ephemeral and records
nothing. Tasks marked interactive = true cannot run from in here; ask the
user to run them on the host.

Run min with no arguments for this sandbox's authoritative subcommand list.
Use the minimal-sandbox skill when you need more detail than that.
EOF

# Escape for embedding as a JSON string: backslashes, then quotes, then newlines.
context="${context//\\/\\\\}"
context="${context//\"/\\\"}"
context="${context//$'\n'/\\n}"

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$context"
