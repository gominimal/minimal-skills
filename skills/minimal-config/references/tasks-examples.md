# Annotated task recipes

Full schema: https://minimal.dev/docs/reference/tasks
Run with `mip run <task>` (Linux, one-shot) or `min run <task>` in a session.

## Arguments: types, enums, defaults, interpolation

```toml
[tasks.greeter]
args.name = "string"                     # No default: mandatory flag --name.
args.greeting = { type = "string", help = "salutation", default = "Hello" }
exec = "echo %{greeting} %{name}"        # Nickel interpolation, not $VAR.

[tasks.deploy]
args.env = ["staging", "prod"]           # Enum: only these values accepted.
exec = "railway up --environment %{env}"
```

`mip run greeter --name world` fills `%{name}`. Types: `"string"`,
`"number"`, `"boolean"`, `"Array string"` (and other Array forms), or an
enum written `["a", "b"]`.

## exec vs bash vs echo

```toml
[tasks.build]
exec = ["cargo", "build", "--release"]   # One command; argv-list form.

[tasks.reset-db]
bash = "dropdb dev || true && createdb dev && psql dev < schema.sql"

[tasks.docs]
echo = "Docs live at https://minimal.dev/docs/reference/minimal-dot-toml"
# echo composes no sandbox at all; use it for pointers and reminders.
```

## Environment, host files, persistent state

```toml
[tasks.integration]
packages = ["postgresql-client"]         # Only this task gets psql.
env_vars.RAILS_ENV = "test"              # Fixed value.
env_vars.GITHUB_TOKEN = { inherit = true }  # Copied from the host env.
patches.dir."~/.aws" = "read-only"       # Host dir, read-only mapping.
patches.file."~/.netrc" = "read-only"    # Single host file.
state_key = "integration"                # Cache state across runs.
inherit_cwd = true                       # Start where invoked, not repo root.
```

Patch paths must be absolute or start with `~/`; missing host paths are
created empty. Modes: `"read-only"`/`"ro"` or `"read-write"`/`"rw"`.

## Interactive shells and TUIs

```toml
[tasks.shell]
interactive = true                       # TTY and stdin attached.
packages = ["base", "git", "nano"]
exec = "bash -l"
```

After adding or editing any task, validate the file with `mip check`.
