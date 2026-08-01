---
name: minimal-loadouts
description: Use when personalizing Minimal sessions with loadouts, e.g. bringing an editor, dotfiles, shell config, env vars, or personal tooling into min sessions without touching the project's committed minimal.toml, authoring or fixing a loadout TOML file, selecting loadouts at activation, or resolving loadout composition conflicts. Do not use for the project-wide minimal.toml (minimal-config owns that), session lifecycle basics (minimal-setup), or dotfile management outside Minimal.
---

# Minimal loadouts

A loadout is a per-developer bundle of packages, env vars, and file patches
layered onto the sessions you activate. The project's `minimal.toml` declares
what every contributor needs; a loadout carries what YOU want on top. Direct
personal tooling (editors, multiplexers, dotfiles) into a loadout, never into
the committed `minimal.toml`. Full schema and composition rules:
https://minimal.dev/docs/reference/loadouts

## Files and selection

- One TOML file per loadout at `<config>/minimal/loadouts/<name>.toml`
  (`~/.config/minimal/loadouts/` on both Linux and macOS). The directory is
  not created automatically.
- The filename stem MUST equal the `name` field inside the file, or loading
  fails with a `NameMismatch` error naming both.
- Apply with `min session activate --loadout NAME` (repeatable). Set
  `[loadouts] default_loadouts = ["NAME"]` in `<config>/minimal/config.toml`
  to apply automatically; any explicit `--loadout` overrides the defaults,
  and `--no-loadouts` skips them all.
- `min loadout list` shows every loadout with its description.

## Authoring

```toml
name        = "dev"
description = "helix + zellij with my dotfiles"
packages    = ["helix", "zellij"]

patches = [
    { dest = ".config/helix/config.toml", source = "~/dotfiles/helix/config.toml" },
    { dest = ".config/helix/themes/",     source = "~/dotfiles/helix/themes/**/*.toml" },
]

[vars]
EDITOR = "hx"
PAGER  = { inherit = true, default = "less" }
```

Directives that prevent the common failures:

- `[vars]` values take three forms: a literal, `{ inherit = true }` (from
  the host env; silently dropped with a warning when unset), or
  `{ inherit = true, default = "..." }`. `inherit = false` is rejected;
  omit the variable instead. Non-POSIX-shaped names need `[[vars_lenient]]`.
- `patches` sources anchor to the host: `~` expands to the host home, the
  expanded path must be absolute, globs need a literal directory prefix
  (`~/dotfiles/**/*.lua` works, bare `**/*.lua` is rejected), and `..` is
  rejected everywhere. `dest` is relative to the session home; for glob
  sources it is a directory. A missing source is dropped with a warning,
  so opportunistic dotfile patches are safe.
- `packages` names are not checked at activation; an unknown package fails
  later at session spawn with `no such package`.
- `[[lifecycle_hooks]]` are composed and recorded with the session, but in
  the current release they are NOT executed. Do not promise boot-time
  behavior from a hook.

## Shell personalization: use vars, not rc files

The attach shell is `bash --noprofile -l` and sources NO startup files, so
patching `.bashrc`/`.bash_profile` does nothing to it. Set shell config
through `[vars]` instead: `PS1` in `[vars]` replaces the stock prompt, and a
once-only banner ships as a `PROMPT_COMMAND` payload that unsets itself.
Patch rc files only for tools that read them explicitly.

## Composition rules

Contributions from the project and every applied loadout compose into one
session; when they clash:

- Same package twice: deduplicated.
- Same var name, same value: deduplicated. Same name, DIFFERENT values: a
  hard conflict that fails activation; there is no override precedence. Fix
  the clash or add the name to the `ignore` list in your user policy.
- Same patch dest with different sources: likewise a conflict.
- Two loadouts with the same name cannot be applied together.

Loadout items also pass through the user policy
(`<config>/minimal/user_policy.toml`): a `deny` pattern fails the
composition client-side before the daemon is involved. A missing policy
file is an empty policy and activates fine.
