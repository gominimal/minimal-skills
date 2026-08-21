# Eval contract

Binding contract between skill authors, case authors, the eval harness, and CI.
Change this file only with a matching change to everything that consumes it.

## Public docs URL contract

Skills link the canonical `minimal.dev` URLs. Verified live 2026-07-31; the
`docs.minimal.dev` redirect BREAKS for guide pages, never use that host.

| Source in gominimal/minimal | Published URL | Linkable |
|---|---|---|
| `docs/reference/<page>.md` | `https://minimal.dev/docs/reference/<page>` | yes |
| `docs/concepts/<page>.md` | `https://minimal.dev/docs/concepts/<page>` | yes |
| `docs/guide/<page>.md` | `https://minimal.dev/start/<page>` | NO: auth-gated |

`/start/` pages currently 302 to `https://minimal.dev/auth/login` for both
real and nonexistent pages, so they are neither publicly readable nor
liveness-checkable. Skills must not link them until that changes; cover the
material via the reference/concepts pages or inline. A URL whose redirect
chain lands on `/auth/` counts as DEAD for `docs_urls_valid` and
`--lint-urls`.

Nothing else is published (`docs/internal/`, `docs/specs/`, `docs/spikes/`,
and docs root pages are private; never link them, never link file paths).
Unknown `/docs/` pages return real 404s, so liveness checks are meaningful.

## SKILL.md rules

- YAML frontmatter: `name` (kebab-case, matches directory) and `description`.
  The description is the trigger; write it as "Use when <positive intents>.
  Do not use for <negative scope>." Aim under 500 chars.
- Body: direct imperative directives ("Always pass `--no-prompt` in
  scripts"), not passive notes. Under ~150 lines. Link a docs URL instead of
  restating anything the public docs cover. No em-dashes.
- The `minimal-networking` skill is the one exception to link-first: its
  surface has no public docs, so it carries inline knowledge and its
  description must say it is experimental and subject to change.

## Case dataset

One file per skill: `evals/cases/<skill>/cases.json`, a JSON array.

```json
{
  "id": "setup-001",
  "prompt": "set up this repo so I can develop it in a sandbox",
  "should_trigger": true,
  "tier": "text",
  "suite": "regression",
  "trials": null,
  "allowed_tools": ["Skill"],
  "expected_checks": [
    "uses_min_init",
    { "name": "response_matches", "args": { "pattern": "min session activate" } }
  ],
  "functional_asserts": []
}
```

Field semantics:
- `id`: `<skill-short>-NNN`, unique across the repo.
- `should_trigger`: `true` = the skill owning this file must fire; `false` =
  NO minimal-* skill may fire (negative case). Negative cases need no
  `expected_checks`.
- `tier`: `"text"` (no command execution; default `allowed_tools`
  `["Skill"]`) or `"functional"` (runs on a machine with minimal installed;
  default `allowed_tools` `["Skill", "Bash", "Read", "Write", "Edit"]`).
- `suite`: `"regression"` (must pass 100%, gates CI) or `"capability"`
  (advisory; graduates to regression once it holds at 100%).
- `trials`: null = runner default (PR 1, nightly 3).
- `functional_asserts`: shell commands run in the case workspace after the
  agent finishes; every command must exit 0 for the case to pass.
- `workspace_files` (optional): object of `"relative/path": "content"`
  written into the workspace before the trial. Use it whenever the prompt
  says "this project": an empty workspace makes such cases ill-posed and a
  well-behaved agent will ask for the missing context instead of answering.

Every skill's file must include at least 2 negative cases. 10-20 cases per
skill total.

## Check registry

`expected_checks` entries are either a bare name (no-arg check) or
`{"name": ..., "args": {...}}`. Implemented in `evals/checks.py` as
`CHECK_REGISTRY: dict[str, Check]`; each check gets `(args, result)` where
`result` has `.response_text`, `.events` (parsed stream-json), and
`.workspace` (Path).

Parameterized:
| name | args | passes when |
|---|---|---|
| `response_matches` | `pattern` | regex (case-insensitive, multiline) matches response text |
| `response_not_matches` | `pattern` | regex does not match |
| `workspace_file_exists` | `path` | file exists in workspace |
| `workspace_file_matches` | `path`, `pattern` | file exists and regex matches its content |

Named (no args):
| name | passes when |
|---|---|
| `docs_urls_valid` | every `https://minimal.dev/...` URL in the response returns HTTP 200 |
| `cites_docs_url` | response cites at least one `minimal.dev/start/` or `minimal.dev/docs/` URL |
| `uses_min_init` | response recommends or runs `min init` |
| `activate_no_prompt` | every scripted/non-interactive `min session activate` in the response carries `--no-prompt` |
| `pins_upstream` | any emitted `minimal.toml` has an `[upstream]` with `locked_commit` |
| `mip_check_suggested` | response suggests `mip check` (or in-session `min check`, the macOS path) to validate config |
| `min_bug_suggested` | response suggests `min bug` for diagnostics |
| `no_hidden_flag_leak` | response does NOT recommend `--network` or `--ingress` (use on setup/config cases; networking cases simply omit it) |
| `no_host_package_manager` | no command line invokes a host package-manager install (apt/apk/dnf/yum/brew install, system pip install, global npm install, cargo install), including forms carrying options such as `apt-get -y install` |
| `routes_to_sandbox_reference` | response resolves the in-sandbox command surface from a live source: run bare `min`, cite the sandbox-operations reference, or explicitly decline to guess a verb when no shell is available to check with. Prefer this over asserting specific `min` syntax, which changes between daemon releases |
| `no_host_only_commands` | response does NOT mention host-only Minimal commands (`min session/init/ls/stop/bug/loadout/update`, any `mip` invocation including `mip --help`); blunt whole-text scan, use only on cases where a host command is never warranted. Citing the `cli-mip` reference URL is not an invocation and does not fail |
| `correct_proxy_port` | networking answers use port 7654 for the routing proxy |
| `host_alias_ip_correct` | response gives `100.64.255.254` for reaching the host from inside a session |

Case authors: use this vocabulary only. A case needing a new named check adds
it to this table in the same change that implements it in `checks.py`.

## Runner CLI

`uv run evals/runner.py` with:

```
--skill NAME        repeatable; default all skills
--tier text|functional|all      default text
--suite regression|capability|all   default all
--trials N          default 1
--without-skill     obsolescence mode: skills not installed into the workspace
--judge             enable the LLM style judge (off by default)
--model M           model passed to claude CLI; default sonnet
--skip-permissions  pass --dangerously-skip-permissions (CI containers only)
--report PATH       write the JSON report
--summary PATH      write a markdown summary (CI appends to $GITHUB_STEP_SUMMARY)
--lint-urls         no-LLM mode: every minimal.dev URL in skills/*/SKILL.md must return 200; exits nonzero on any failure
```

Mechanics: per trial, fresh temp workspace; unless `--without-skill`, every
skill directory is copied to `<workspace>/.claude/skills/` (trigger realism:
the right one must fire, and for negatives none may). Invocation:
`claude -p <prompt> --output-format stream-json --verbose --max-turns 10`
with `--allowedTools` from the case, cwd = workspace. Text tier additionally
passes `--disallowedTools` for every execution/mutation tool not explicitly
allowed by the case: `--allowedTools` only pre-approves, it does not
restrict, so without the deny a local run inherits the developer's own
permission allowlists and a "text" case can run real commands on their
machine. Trigger detection = a Skill tool_use event naming a minimal-*
skill.

Pass rules: trial passes if trigger expectation holds and all
`expected_checks` (and `functional_asserts`) pass. Regression case passes
only if ALL trials pass; capability case if >=50% of trials pass. Exit code
is nonzero iff any regression case fails.

Infra errors are not verdicts: a claude invocation that itself fails (no
events, an error result, or nonzero exit with no result event; rate limits
and auth failures look like this) is retried twice with backoff (15s, 45s)
before the trial is recorded as failed with `reason: "infra_error"`. CI
jobs that share the one CLAUDE_CODE_OAUTH_TOKEN must also be serialized,
not run concurrently, or they exhaust its rate limit mid-run.
