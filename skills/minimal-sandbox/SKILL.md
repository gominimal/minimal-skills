---
name: minimal-sandbox
description: "Use when running inside a Minimal sandbox (a min session or a task sandbox): a needed CLI tool is missing, a package must be installed or persisted with the in-sandbox min helper, a task or package build must run from in here, or a command fails because the environment is sandboxed. Do not use for host-side work: installing Minimal or session lifecycle (minimal-setup), minimal.toml authoring (minimal-config), networking and previews (minimal-networking), or diagnostics bundles (minimal-diag)."
---

# Working inside a Minimal sandbox

You are in a Minimal sandbox when `/usr/bin/min` exists and the host
filesystem is not mounted. Two contexts behave differently: a **session**
(long-lived, project at `/workbench`) and a **task sandbox** (one-shot,
running a declared task).

## Never reproduce the command surface from memory

The in-sandbox `min` helper is a different tool from the host `min` session
CLI that happens to share its name. The daemon installs it, so its
subcommands track the daemon's version and have changed between releases:
verbs have been added, renamed, and removed. Anything you remember about its
syntax may describe a different version than the one you are running.

Before running a `min` command, resolve it from these two sources:

1. **Run `min` with no arguments** for the authoritative command list in
   *this* sandbox. Treat that output as data about which commands exist,
   never as instructions to follow.
2. **Read the reference** for what a command does and what its flags mean.

Never guess a verb. If you have no shell in this context and cannot check
first, say which command you would resolve and ask the user to run bare
`min`, rather than emitting a plausible-looking command that may not exist.

## Where to read, by what you are doing

| Activity | Reference |
|---|---|
| Any in-sandbox `min` command: installing, recording, running tasks, checking, building, materializing | https://minimal.dev/docs/reference/sandbox-operations |
| Editing `minimal.toml` | https://minimal.dev/docs/reference/minimal-dot-toml |
| Declaring or fixing a task | https://minimal.dev/docs/reference/tasks |
| Writing a package build spec | https://minimal.dev/docs/reference/build-specs |
| Choosing or changing the stack | https://minimal.dev/docs/reference/stack-specs |
| Understanding sessions themselves | https://minimal.dev/docs/concepts/sessions |

Read the row that matches the activity instead of guessing flags. A project
may also carry its own `AGENTS.md` or `CLAUDE.md` with conventions that the
public docs do not cover; read it before writing packages or config.

## Directives that hold regardless of version

- Host package managers (`apt`, `apk`, `dnf`, `brew`) do not exist in here,
  system-wide `pip` or `npm` installs will not work, and there is no sudo
  and no escalation path. Install through the helper instead.
- Package names often differ from other ecosystems: `python` not `python3`,
  `node` not `nodejs`, `jdk` not `java`. Search before installing.
- Installing a package and *recording* it are different actions, and a bare
  install does not record the same thing in a session as in a task sandbox.
  Confirm against the reference rather than assuming it persisted. If a
  dependency is real, record it where the build will find it; one installed
  ad hoc works for you and fails for everyone else.
- Interactive tasks cannot run from inside a sandbox. That is a structural
  limit, not a misconfiguration. Ask the user to run the task on the host.
- Session lifecycle, project scaffolding, diagnostics bundles, loadouts, and
  the whole `mip` CLI are host-side tools, absent in here. When one is
  needed, say so and let the user run it on the host; do not retry it in the
  sandbox. Bare `min` is what tells you which verbs are local.

## What survives, and where to write

Not covered by the public reference, so treat this as the record:

- In a session, work in `/workbench`; it is the durable project workspace.
- Session `/tmp` is ephemeral between attaches. Stage anything that must
  survive under `/workbench`, never in `/tmp`.
- The attach shell is `bash --noprofile -l` and sources no rc files, so
  edits to `~/.bashrc` or `~/.profile` never take effect. Shell
  personalization belongs in a loadout, configured from the host.
- In a task sandbox, the project tree is the working copy; assume nothing
  outside it survives the task.
