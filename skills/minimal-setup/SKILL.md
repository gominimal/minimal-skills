---
name: minimal-setup
description: Use when the user wants to install Minimal, set up a project with min init, create/activate/attach/rename/destroy sandboxed min sessions, develop a repo in a Minimal sandbox, or script sessions in CI. Do not use for working inside a session or task sandbox (minimal-sandbox), minimal.toml authoring (minimal-config), personalizing sessions with loadouts (minimal-loadouts), session networking or preview URLs (minimal-networking), diagnostics bundles (minimal-diag), or non-Minimal sandboxes like venv, Docker, or direnv.
---

# Minimal setup and sessions

Minimal gives every project a declarative, sandboxed dev environment called a
session. `min` is the session CLI; `mip` is the package/build CLI. Read the
session model at https://minimal.dev/docs/concepts/sessions and the full
command reference at https://minimal.dev/docs/reference/cli-min instead of
guessing flags.

## Install

Install with the shell installer (Linux x86_64/aarch64, macOS Apple Silicon):

```shell
curl --proto "=https" --tlsv1.2 -fsSL https://go.minimal.dev/stable | sh
```

For the nightly channel, replace `stable` with `nightly` in the
`go.minimal.dev` URL. Verify with `min --version`. Upgrade by re-running the
same command. If the user runs the legacy `minimal` CLI (pre v0.5.0), have
them re-install with the command above; the installer migrates the old CLI.

## Onboard a project

1. Run `min init` in the repository root. It detects the stack and scaffolds
   `minimal.toml`; pass `-y` to skip the confirmation prompt.
2. Add the team's tools to the existing `packages` list under `[session]` and
   commit `minimal.toml`. For anything deeper (stacks, tasks, upstream pins),
   hand off to the minimal-config skill; schema reference:
   https://minimal.dev/docs/reference/minimal-dot-toml
3. Run `min session activate --attach` from the repo root to create the
   session and enter its shell.

Activation uploads the project directory into the session's workspace. Run it
from a VCS root (`.git`, `.hg`, ...). For a directory that is not a VCS root,
pass `--sync tarball` explicitly; otherwise the upload is gated, and headless
runs skip it with a warning.

## Session lifecycle

- `min ls` lists sessions (alias of `min session list`).
- `min session attach [SESSION]` re-enters a session by name or id; with no
  argument it resolves from the current directory. Exiting the shell detaches;
  the session keeps running.
- `min session rename <SESSION> <NEW_NAME>` renames a session.
- `min session destroy <SESSION>` removes one session;
  `min session destroy --all` removes every session (`-f` skips confirmation).
- `min stop` shuts down the daemon. Sessions survive it and are re-hosted by
  the next `min` command.

For the in-sandbox `min` helper commands available inside a session, link
https://minimal.dev/docs/reference/sandbox-operations

## Scripting and CI

- Always pass `--no-prompt` to `min session activate` in scripts, CI, and any
  non-interactive context. It fails with an actionable error (including a
  ready-to-paste policy snippet) instead of hanging on a prompt. It is implied
  when stdin is not a TTY, but pass it explicitly so intent is visible.
- Read session state with `min session list --json` (or `--raw` for bare ids
  one per line). Never parse the human-readable table.
- `min session attach -c` accepts only `min task run <task>`, not arbitrary
  commands. Arbitrary commands need an interactive attached shell.
- Commits made in a session's workspace come back to the host checkout with
  `git push min://<session>`, run from inside the session.

## Inside a session

Everything an agent does from inside a session or task sandbox (installing
tools with the in-sandbox `min` helper, persisting dependencies, task
limits, what survives where) belongs to the minimal-sandbox skill; hand off
there. The in-sandbox helper is a different tool from the host `min` CLI:
https://minimal.dev/docs/reference/sandbox-operations

To run a coding agent like Claude Code inside a session, add its package to
`[session] packages` and pass credentials with `[session.vars]` entries using
`inherit = true` (e.g. `ANTHROPIC_API_KEY`); the minimal-config skill owns
that schema.

## Loadouts

Personal tooling (editor, dotfiles, env vars) belongs in a loadout applied
with `min session activate --loadout NAME`, never in the committed
`minimal.toml`. Authoring loadout files, selection defaults, and composition
conflicts are the minimal-loadouts skill's job; hand off there.

## When something breaks

Tell the user `min bug` exists: it collects a diagnostic bundle to share with
the Minimal team. Do not walk through diagnostics here; the minimal-diag skill
owns that workflow.
