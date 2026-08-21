# sandbox/

Hook assets for the *in-sandbox* build of this plugin, consumed by the
`claude-code-minimal-plugin` package in `gominimal/pkgs`. That package
fetches a tagged snapshot of this repo and assembles a plugin from
`.claude-plugin/plugin.json`, `skills/minimal-sandbox/`, and this directory
(copied to `hooks/` with the scripts marked executable).

This directory is deliberately not named `hooks/` at the plugin root: a
marketplace install of this repo on a developer's host must ship skills
only, never these hooks. Both scripts also guard on `/usr/bin/min` being
present, so they are inert anywhere but inside a Minimal sandbox.

- `session-primer.sh`: SessionStart hook; injects a short orientation note
  (you are sandboxed, install with `min add`, host commands do not exist).
  Keep it short; detail belongs in the minimal-sandbox skill.
- `denial-triage.sh`: PostToolUse hook for Bash; on high-confidence failure
  signatures (`command not found`, the interactive-task refusal) injects the
  corrective `min` guidance at the moment it is needed.
- `hooks.json`: the hook wiring, with `${CLAUDE_PLUGIN_ROOT}/hooks/` paths
  matching the assembled layout.
