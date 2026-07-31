# Annotated minimal.toml: Rust project

A trimmed real-world config (Minimal builds itself with it). Schema:
https://minimal.dev/docs/reference/minimal-dot-toml

```toml
[upstream]                       # Pinned source of packages/stacks/profiles.
repo = "https://github.com/gominimal/pkgs"
branch = "main"
locked_commit = "d299744531767b2edeb5b0ead2178dadc40bbeed"  # Full hash; only `mip update` rewrites it.

[stack]
use = "rust"                     # `mip run build` becomes `cargo build --release`.
runtime_packages = ["socat"]     # Extra deps beyond what the stack ships.

[defaults]
profile = "dev"                  # Applied to tasks that set no profile.
state_key = "dev"                # Tasks sharing a state_key share cached state.

[session]
packages = ["just", "protobuf"]  # Tools every contributor's session gets.

[tasks.test]
exec = "cargo test --verbose"
inherit_cwd = true               # Run where invoked, not at the repo root.

[tasks.shell]
interactive = true               # TTY + stdin attached.
exec = "bash --noprofile -l"

[tasks.ci]
inherit_cwd = true
bash = """
set -e
cargo test --verbose
cargo fmt -- --check
cargo clippy --all-targets -- -D warnings
"""

# Built with: mip materialize bash-img -o ./bash.tar
[outputs.bash-img]
type = "oci-image"
packages = ["bash", "coreutils", "tar"]
cmd = ["/usr/bin/bash", "-l"]
```

Notes:

- `locked_commit` makes the supply chain reproducible; never delete it, and
  never refresh it (`mip update`) unless asked.
- `inherit_cwd` matters for cargo tasks in workspaces: without it the task
  always runs at the repo root.
- Run `mip check` after editing; it validates packages, stacks, and profiles.
