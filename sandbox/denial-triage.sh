#!/bin/bash
# PostToolUse (Bash) hook: when a command inside a Minimal sandbox fails in a
# way that usually means "missing tool" or "host-only operation", inject a
# short corrective note so the agent reaches for `min` instead of a host
# package manager or a retry loop.
#
# Deliberately narrow: it matches only high-confidence signatures in the raw
# hook payload and stays silent otherwise. No jq dependency; the payload is
# only pattern-matched, never parsed.
set -euo pipefail

# Stay silent outside a Minimal sandbox, where the shim is not installed.
[ -x /usr/bin/min ] || exit 0

payload=$(cat)

if ! grep -qiE 'command not found|cannot run interactive tasks' <<< "$payload"; then
  exit 0
fi

read -r -d '' context << 'EOF' || true
[Minimal sandbox] That failure usually means a missing tool or a host-only
operation. This environment is a Minimal sandbox: the host filesystem is not
mounted, there is no sudo, and host package managers (apt, apk, dnf, brew)
do not exist. Do not retry the same command, and do not fall back to a
system-wide pip or npm install.

- Missing tool: run `min search <term>` to find the package, then
  `min add <pkg>` to install it into this sandbox. Use `min add --build`
  or `min add --runtime` when the dependency should be recorded.
- Host-only command (min session, min init, min bug, mip, or a task with
  interactive = true): it cannot run from in here. Ask the user to run it
  on the host.

Run min with no arguments for the authoritative in-sandbox command list.
EOF

context="${context//\\/\\\\}"
context="${context//\"/\\\"}"
context="${context//$'\n'/\\n}"

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$context"
