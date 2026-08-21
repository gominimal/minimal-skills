---
name: minimal-sandbox
description: "Use when running inside a Minimal sandbox (a min session or a task sandbox): a needed CLI tool is missing, a package must be installed or persisted with the in-sandbox min helper, a task or package build must run from in here, or a command fails because the environment is sandboxed. Do not use for host-side work: installing Minimal or session lifecycle (minimal-setup), minimal.toml authoring (minimal-config), networking and previews (minimal-networking), or diagnostics bundles (minimal-diag)."
---

# Working inside a Minimal sandbox

You are in a Minimal sandbox when `/usr/bin/min` exists and the host
filesystem is not mounted. The in-sandbox `min` helper is a different tool
from the `min` session CLI on the host that happens to share its name. Full
helper reference: https://minimal.dev/docs/reference/sandbox-operations

The helper is installed by the Minimal daemon and tracks the daemon's
version, not this document. **Run `min` with no arguments to print the
authoritative subcommand list; when this document and that output disagree,
trust the output.**

## Know which sandbox you are in

- A **session**: a long-lived dev sandbox created on the host with
  `min session activate`. The project lands in `/workbench`.
- A **task sandbox**: a one-shot sandbox running a `minimal.toml` task
  (for example the host launched `min run claude` or `mip run test`). The
  project tree is the working directory.

The distinction changes what `min add` records; see below. When unsure,
check for `/workbench` and read the bare `min` output.

## Installing tools

Host package managers (`apt`, `apk`, `dnf`, `brew`) do not exist in here,
and system-wide `pip` or `npm` installs will not work. There is no sudo and
no escalation path. Install with the helper:

```bash
min search ripgrep    # find the package name
min add ripgrep       # install into this sandbox
```

Package names often differ from other ecosystems: `python` not `python3`,
`node` not `nodejs`, `jdk` not `java`. Search first when unsure.

## Where the dependency is recorded

Bare `min add` behaves differently by context:

- In a **session**, `min add <pkg>` defaults to `--session`: it installs
  live and records the package in the `[session]` `packages` list of the
  project's `minimal.toml`.
- In a **task sandbox**, `min add <pkg>` installs for the current sandbox
  only and is ephemeral: `minimal.toml` is not modified.

To persist a dependency where the build needs it, pass a flag:

```bash
min add --build <pkg>      # record in the stack's build packages
min add --runtime <pkg>    # record in the stack's runtime packages
```

If you install with a bare `min add` and then reference the package from
config, the build works for you and fails for everyone else. Record real
dependencies.

## Running tasks

Run the project's declared tasks with `min run <task>`. Interactive tasks
(declared `interactive = true`, conventionally `shell` and `claude`) are
not supported inside a sandbox; that is a structural limit, not a
misconfiguration. Do not try to work around it; ask the user to run the
task on the host.

## Validating and building packages

In a repo with Minimal config or packages, validate and build from in here:

- `min check` lints packages and stacks; run it after any config edit and
  fix everything it reports.
- `min package build <pkg>` runs a full package build.
- `min package patched-build <pkg>` builds one package against the newest
  available builds of its dependencies; use it as the edit-build inner loop.
- `min materialize -o <file> <output>` materializes a declared output.

Details for each: https://minimal.dev/docs/reference/sandbox-operations

## Host-only commands

These exist only on the host and fail in here as unknown commands:
`min session ...`, `min ls`, `min init`, `min stop`, `min bug`,
`min loadout`, `min update`, and the whole `mip` CLI. When one is needed,
tell the user to run it on the host; do not retry it in the sandbox.

## What survives, and where to write

In a session:

- Work in `/workbench`; it is the durable project workspace.
- `/tmp` is ephemeral between attaches. Stage anything that must survive
  under `/workbench`, never in `/tmp`.
- Hand commits back to the host checkout with `git push min://<session>`.
- The attach shell is `bash --noprofile -l` and sources no rc files, so
  edits to `~/.bashrc` or `~/.profile` never take effect. Shell
  personalization belongs in a loadout, configured from the host.

In a task sandbox: the project tree is the working copy; assume nothing
outside it survives the task.
