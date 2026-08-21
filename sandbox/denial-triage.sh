#!/bin/bash
# Bash tool hook: when a command inside a Minimal sandbox fails in a way that
# usually means "missing tool" or "host-only operation", point the agent at
# the right recovery route instead of a host package manager or a retry loop.
#
# Registered on BOTH PostToolUse and PostToolUseFailure, because which one a
# `command not found` (exit 127) delivers is not something we want to bet the
# hook on. The reference defines PostToolUse as "after a tool completes
# successfully" and PostToolUseFailure as "after a tool call fails", and its
# PostToolUseFailure example is a Bash `npm test` exiting 1 with
# `error: "Exit code 1\n..."`, which reads as non-zero exits landing on the
# failure event. If instead the Bash tool reports a non-zero exit as a
# successful tool call, the PostToolUse registration catches it. Handling
# both costs one extra entry and removes the guess.
#
# The two events carry the failure text in different places, so read the
# event name and pick the matching field, and echo that same event name back
# in hookSpecificOutput.
#
# Carries no `min` syntax on purpose: the helper's verbs change between
# daemon releases, and a stale command here would be worse than none. It
# names the two sources that are always current.
#
# Deliberately narrow: it matches only high-confidence signatures and stays
# silent otherwise. The injected text is fixed and never interpolates the
# payload, so a hostile command result cannot ride this hook into the
# model's context.
set -euo pipefail

# Stay silent outside a Minimal sandbox, where the shim is not installed.
[ -x /usr/bin/min ] || exit 0

payload=$(cat)

# Echo back whichever event actually fired; a mismatched hookEventName is
# ignored. Grep rather than jq so this still holds without a JSON parser.
if grep -q '"hook_event_name"[[:space:]]*:[[:space:]]*"PostToolUseFailure"' <<< "$payload"; then
  event=PostToolUseFailure
else
  event=PostToolUse
fi

# Match the failure text alone. `tool_input.command` also rides in the
# payload, so scanning the whole thing lets a failing command whose own text
# carries a signature (`grep "command not found" build.log`) trigger a nudge
# that misreads the failure. PostToolUseFailure carries it in `.error`,
# PostToolUse in `.tool_response`, whose shape is per-tool and undocumented
# for Bash, so take every string in it rather than naming a field.
if command -v jq > /dev/null 2>&1; then
  failure=$(jq -r '[(.error // empty)] + [(.tool_response // empty) | .. | strings] | join("\n")' <<< "$payload")
  signature='command not found|cannot run interactive tasks'
else
  # No JSON parser. Going silent here would disable the hook in most
  # sandboxes, since `base` ships no jq, so drop `tool_input` out of the
  # payload with sed instead and scan what is left. `base` does ship sed.
  # The object is flat for Bash ({command, description}) and escaped quotes
  # inside it are \" rather than a bare brace, so [^{}]* spans the value;
  # a command carrying a literal brace (awk '{print}') leaves the object in
  # place, which is why the signature is anchored as well.
  failure=$(sed -E 's/"tool_input"[[:space:]]*:[[:space:]]*\{[^{}]*\}//g' <<< "$payload")
  # Anchored: bash writes "bash: htop: command not found", with a colon
  # before the phrase, while a command that merely mentions it does not.
  # The interactive-task refusal needs no anchor; a command containing that
  # whole sentence is not a realistic false positive.
  signature=': command not found|cannot run interactive tasks'
fi

if ! grep -qiE "$signature" <<< "$failure"; then
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

printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' "$event" "$context"
