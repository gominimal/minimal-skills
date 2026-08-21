#!/bin/bash
# PostToolUse (Bash) hook: when a command inside a Minimal sandbox fails in a
# way that usually means "missing tool" or "host-only operation", point the
# agent at the right recovery route instead of a host package manager or a
# retry loop.
#
# Carries no `min` syntax on purpose: the helper's verbs change between
# daemon releases, and a stale command here would be worse than none. It
# names the two sources that are always current.
#
# Deliberately narrow: it matches only high-confidence signatures in the raw
# hook payload and stays silent otherwise. The injected text is fixed and
# never interpolates the payload, so a hostile command result cannot ride
# this hook into the model's context. No jq dependency; the payload is only
# pattern-matched, never parsed.
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

- Missing tool: install it with the `min` helper on PATH. Run `min` with no
  arguments for this sandbox's command list, and see
  https://minimal.dev/docs/reference/sandbox-operations for the flags that
  decide whether the dependency is recorded as well as installed.
- Host-only operation (session lifecycle, project scaffolding, diagnostics,
  `mip`, or a task declared interactive): it cannot run from in here. Ask the
  user to run it on the host.

Do not run a `min` command from memory; its subcommands change between
daemon releases. The minimal-sandbox skill covers the rest.
EOF

context="${context//\\/\\\\}"
context="${context//\"/\\\"}"
context="${context//$'\n'/\\n}"

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$context"
