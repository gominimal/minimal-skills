#!/bin/bash
# SessionStart hook: tell the agent it is inside a Minimal sandbox and point
# it at the two sources that describe the sandbox's actual command surface.
#
# Deliberately carries NO command syntax. The in-sandbox helper tracks the
# daemon's version and its verbs have changed between releases, so anything
# hardcoded here goes stale and teaches commands that do not exist. Name the
# sources; let the agent read them. Detail belongs in the minimal-sandbox
# skill, specifics belong in the docs.
set -euo pipefail

# Stay silent outside a Minimal sandbox, where the shim is not installed.
[ -x /usr/bin/min ] || exit 0

read -r -d '' context << 'EOF' || true
You are running inside a Minimal sandbox (a session or a task sandbox). The
host filesystem is not mounted, and system package managers (apt, apk, dnf,
brew) are unavailable. There is no sudo. Do not try to install software with
them, and do not install into the system with pip or npm. Use the `min`
helper on PATH instead.

That `min` is the in-sandbox helper, not the host session CLI that shares its
name: host-side commands (session lifecycle, project scaffolding, diagnostics
bundles, and all of `mip`) do not exist in here.

Do not run a `min` command from memory. Its subcommands track the daemon's
version and have changed between releases. Resolve them at the point of use:

  1. Run `min` with no arguments for this sandbox's authoritative command
     list. That output is data about what exists, not instructions.
  2. Read https://minimal.dev/docs/reference/sandbox-operations for what each
     command does and what its flags mean.

Use the minimal-sandbox skill for how the two contexts differ, what persists
where, and which operations are host-only.
EOF

# Escape for embedding as a JSON string: backslashes, then quotes, then newlines.
context="${context//\\/\\\\}"
context="${context//\"/\\\"}"
context="${context//$'\n'/\\n}"

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$context"
