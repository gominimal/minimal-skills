# Annotated task recipes

Worked examples of how task keys compose. The schema is authoritative for
every key, type, and default: https://minimal.dev/docs/reference/tasks

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

Running the task with `--name world` fills `%{name}`. The schema lists the
accepted arg types.

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

Map host paths read-only unless the task genuinely writes them. An inherited
env var is readable by everything the task runs, so inherit sparingly and
prefer short-lived tokens.

## Interactive shells and TUIs

```toml
[tasks.shell]
interactive = true                       # TTY and stdin attached.
packages = ["base", "git", "nano"]
exec = "bash -l"
```

After adding or editing any task, validate the file and fix everything the
check reports.
