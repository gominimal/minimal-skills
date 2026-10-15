<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/minimal-mark-light.svg">
    <img src="assets/minimal-mark-dark.svg" alt="Minimal logo" width="120">
  </picture>
</p>

<h1 align="center">minimal-skills</h1>

Claude Code skills for the [Minimal](https://minimal.dev) developer system, packaged as
a plugin, plus the eval pipeline that keeps them honest. Each skill teaches
Claude Code how to drive one slice of Minimal (setup, configuration,
networking, diagnostics), and every skill is continuously tested for trigger
accuracy, answer quality, and drift against the published docs.

## Install

```
claude plugin marketplace add gominimal/minimal-skills
claude plugin install minimal@gominimal
```

Or run `/plugin` inside the Claude Code REPL and install `minimal` from the
`gominimal` marketplace.

## Skills

| Skill | What it does |
|---|---|
| `minimal-setup` | Get a repo running in the Minimal developer system: install, `min init`, session creation and activation. |
| `minimal-sandbox` | Work correctly from inside a sandbox (session or task sandbox): the in-sandbox `min` helper, installing and persisting packages, task limits, what survives where. |
| `minimal-config` | Author and validate `minimal.toml`: packages, stacks, upstream pinning, `mip check`/`min check`. |
| `minimal-loadouts` | Personalize sessions with per-developer loadouts: editors, dotfiles, env vars, patches, composition rules. |
| `minimal-networking` | Session networking: `--network` modes, egress rules, `.min.internal` names, publishing and forwarding ports, `min finalize-install`. |
| `minimal-diag` | Diagnose broken sessions and builds: `min bug` support bundles, uploading one for diagnosis with `min bug --upload` or `min diag upload`, deleting it with `min diag delete`. |

## Eval pipeline

Two tiers, two canaries. The binding contract for cases, checks, and the
runner CLI is [evals/SCHEMA.md](evals/SCHEMA.md); the methodology follows
[Testing Agent Skills](https://www.philschmid.de/testing-skills).

- **PR text tier**: every pull request runs a no-secrets URL lint, then the
  text-tier suite (does the right skill trigger, does no skill trigger on
  negative cases, does the response pass its checks). One trial per case;
  regression cases gate the merge.
- **Nightly functional tier**: the full suite (3 trials) on runners with a
  real Minimal installed from both the `stable` and `nightly` channels, so a
  Minimal release that breaks a skill surfaces within a day.
- **Obsolescence canary** (nightly, advisory): the text tier re-run with the
  skills not installed. When the bare model passes everywhere, a skill has
  stopped paying rent and should be slimmed or retired.
- **Docs-drift canary** (nightly): the published `minimal.dev` pages the
  skills link are hashed and compared to `evals/docs-snapshots.json`; a
  changed page fails the run so the skill gets re-checked against it.

Failures of blocking nightly jobs open or update a single tracking issue.

## Dev loop

Needs the `claude` CLI on PATH, authenticated (locally via `claude` login; CI passes a `CLAUDE_CODE_OAUTH_TOKEN` secret generated with `claude setup-token`)
(`npm install -g @anthropic-ai/claude-code`); `lint-urls` and `lint-parity` need neither.

```
just lint-urls        # liveness-check every docs URL in the skills
just lint-parity      # assert the minimal README's three-command block matches minimal-setup
just eval             # text tier, all skills, 1 trial
just eval-skill minimal-setup   # text tier, one skill
just triggers         # fast trigger-accuracy pass
just functional       # functional tier; needs a local Minimal install
just obsolescence     # text tier with the skills not installed
just report           # open the latest JSON report
```

## Repo layout

```
.claude-plugin/       plugin and marketplace manifests
skills/               one directory per skill, each with a SKILL.md
sandbox/              hook assets for the in-sandbox build (gominimal/pkgs)
evals/                eval harness: runner.py, checks.py, cases/, SCHEMA.md
.github/workflows/    pr-evals.yml (PR gate), nightly-evals.yml (nightly tier)
justfile              local dev-loop recipes
```

## Notes

- Skills link the published docs at `minimal.dev` instead of restating them;
  the URL contract lives in [evals/SCHEMA.md](evals/SCHEMA.md).
- Behavior claims are checked against a real install, and anything the
  reference documents is linked rather than restated. The 0.7.0 pass was
  verified on 2026-10-14 against min 0.7.0-rc2 (macOS arm64): network modes,
  egress defaults, `.min.internal` names, `min net forward`, static and
  dynamic ingress, `min bug --upload` and `min diag delete`, and the
  `min session run` environment trap. The 0.6.0 pass was verified on
  2026-09-25 against min 0.6.0 staged from minimal 9b763dd5 (macOS arm64).
  The 0.4.0 pass was verified on 2026-09-03 against min
  0.5.4-dev.62.g30a3031d (macOS arm64, minvmd + gvproxy); reference gaps
  found on that pass are filed as
  [#622](https://github.com/gominimal/inbox/issues/622),
  [#623](https://github.com/gominimal/inbox/issues/623) and
  [#624](https://github.com/gominimal/inbox/issues/624) in gominimal/inbox.
- `minimal-networking` is link-first since 0.7.0, when the cli-min and tasks
  references gained the networking surface. Two places where the running
  0.7.0-rc2 and the published docs disagree are recorded inline rather than
  linked: `--dynamic-ingress allow` works on a macOS host, and an `own_ip`
  session on macOS does not reach `host.min.internal` or the host-side proxy.
  Filed as
  [#1093](https://github.com/gominimal/inbox/issues/1093),
  [#1094](https://github.com/gominimal/inbox/issues/1094) and
  [#1095](https://github.com/gominimal/inbox/issues/1095) in gominimal/inbox.
- Sandboxed Claude Code sessions get this content through the
  `claude-code-minimal-plugin` package in `gominimal/pkgs`, which fetches a
  tagged snapshot of this repo and assembles `skills/minimal-sandbox/` plus
  the `sandbox/` hooks into an in-sandbox plugin. A marketplace install on a
  developer host ships the skills only, never the hooks.

## License

MIT, see [LICENSE](LICENSE).

Note: the optional LLM style judge (`--judge`) uses the Anthropic SDK and
needs `ANTHROPIC_API_KEY`; the default pipeline authenticates the `claude`
CLI alone and never requires it.
