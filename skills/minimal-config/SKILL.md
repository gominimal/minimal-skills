---
name: minimal-config
description: "Use when writing or editing minimal.toml, adding a package or tool to a project's Minimal config, defining or fixing a Minimal task, pinning or updating the [upstream], resolving mip check errors, explaining unexpected minimal.toml changes such as rewritten locked_commit lines, or choosing a stack, profile, or output for the Minimal build system. Do not use for session lifecycle or CLI usage (minimal-setup owns those), generic TOML syntax questions, or other manifests such as Cargo.toml or package.json."
---

# Authoring and validating minimal.toml

`minimal.toml` is the declarative config for Minimal: the package/build plane
(`mip` CLI) and sandboxed dev sessions (`min` CLI). Full schema:
https://minimal.dev/docs/reference/minimal-dot-toml

## Non-negotiables

- Place `minimal.toml` at the repo root, or in `.minimal/` at the repo root.
  `mip` searches upward from the cwd, so commands work from subdirectories.
- Always pin `[upstream]`: every minimal.toml you emit must carry `repo`,
  `branch`, and a full `locked_commit` hash. Never leave an upstream unpinned.
- Never run `mip update` as a side effect of other work. It re-resolves
  `branch` to its current HEAD and rewrites `locked_commit` in place for the
  upstream and every sideload. Run it only when the user explicitly wants new
  pins, and tell them to expect a diff on those fields.
- Always run `mip check` after any minimal.toml change (hand edit or
  `min add`) and fix everything it reports. `mip check --fix` attempts
  automatic fixes. CLI details: https://minimal.dev/docs/reference/cli-mip

## Scaffolding vs hand-authoring

- Scaffold new projects with `min init` (a passthrough to `mip init`): it
  inspects the source tree, detects the stack (Rust, Go, pnpm, npm, uv, and
  more), and proposes a minimal.toml; pass `-y` to skip the confirmation
  prompt.
- Whenever you create a minimal.toml or explain creating one, state that it
  requires a pinned `[upstream]` (repo, branch, and a full `locked_commit`
  hash); `min init` writes one, and an unpinned config does not resolve.
- Hand-author only when detection picks wrong or the layout is unusual, and
  still finish with `mip check`.

## Sections, one line each

- `[upstream]`: the pinned git source of packages, stacks, and profiles;
  `[[upstream.sideload]]` entries add more repos with the same pinned schema.
- `[stack]`: names how the codebase builds (`use = "rust"`); stacks are
  Nickel specs, see https://minimal.dev/docs/reference/stack-specs
- `[defaults]`: `profile` and `state_key` applied to every task that does not
  set its own.
- `[session]`: packages, vars, and patches every contributor's dev session
  gets on this project.
- `[tasks.<name>]`: named sandboxed commands.
- `[outputs.<name>]`: artifacts built by `mip materialize <name> -o <path>`
  (`oci-image` by default, or `raw-file`).
- `[params]`: repo-wide task arguments; every entry must declare a `default`.
- Packages are the unit of software: project-local ones are Nickel build
  specs in `packages/<name>/build.ncl`, see
  https://minimal.dev/docs/reference/build-specs
- Profiles are reusable task customizations in `profiles/<name>/profile.ncl`,
  see https://minimal.dev/docs/concepts/profiles

## Where a package goes

Add each package exactly where it is needed, nowhere else:

| Need | Config | CLI |
|---|---|---|
| Build-time tool | `[stack] build_packages` | `min add --build <pkg>` |
| Runtime library | `[stack] runtime_packages` | `min add --runtime <pkg>` |
| Every dev session | `[session] packages` | `min add --session <pkg>` |
| One task only | `[tasks.<name>] packages` | `min add --task <name> <pkg>` |

## Tasks

```toml
[tasks.test]
description = "Run the test suite"
packages = ["cargo-nextest"]
exec = "cargo nextest run"
inherit_cwd = true

[tasks.greet]
args.name = { type = "string", help = "who to greet", default = "world" }
bash = "echo Hello %{name}"
```

- Give each task exactly one action: `exec` (one command, as a string or an
  argv list), `bash` (a shell script), or `echo` (print a fixed string).
- Bare command names in `exec` resolve to `/bin/<command>` in the sandbox.
- Declare `args` with a datatype: `"string"`, `"number"`, `"boolean"`, an
  array form like `"Array string"`, or an enum written `["a", "b"]`. An arg
  without a `default` is mandatory. Substitute values into the command with
  Nickel interpolation: `%{name}`.
- Set `interactive = true` for shells and TUI apps. Set `state_key` to keep
  build state (like `target/` or `node_modules`) between runs; tasks sharing
  a `state_key` share that state.
- `env_vars.NAME = "value"` sets a variable; `{ inherit = true }` passes the
  host value through. `patches` maps host files or dirs into the task; map
  them `"read-only"` unless the task must write them.
- Run tasks with `mip run <task>` (one-shot sandbox, Linux) or `min run
  <task>` from inside a session on any platform.
- Full task schema: https://minimal.dev/docs/reference/tasks

## Session block

```toml
[session]
packages = ["just", "protobuf"]
patches = [{ source = "config/psqlrc", dest = ".psqlrc" }]

[session.vars]
RUST_LOG     = "info"
DATABASE_URL = { inherit = true, default = "postgres://localhost/dev" }
```

- A string var sets a fixed value; `{ inherit = true }` uses the developer's
  own value, with `default` as the fallback when it is unset.
- Session `patches` are `{ source, dest }` rows: `source` resolves on the
  host (usually in the repo), `dest` is relative to the session home.
- `[session]` carries the same primitives as a loadout but is scoped to the
  project. Loadouts themselves are per-developer files and never live in
  minimal.toml: https://minimal.dev/docs/reference/loadouts

## Out of scope

- Session lifecycle and CLI usage (activate, attach, destroy, debugging a
  session) belong to the minimal-setup skill; defer to it.
- This skill covers Minimal config only, not Cargo.toml, package.json, or
  other ecosystems' manifests.

## References

- `references/minimal-toml-rust.md`: annotated Rust project config.
- `references/minimal-toml-node.md`: annotated pnpm/Node project config.
- `references/tasks-examples.md`: annotated task recipes (args, patches,
  state, interactive).
