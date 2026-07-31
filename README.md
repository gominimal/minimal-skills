<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/minimal-mark-light.svg">
    <img src="assets/minimal-mark-dark.svg" alt="Minimal logo" width="120">
  </picture>
</p>

<h1 align="center">minimal-skills</h1>

Claude Code skills for the [Minimal](https://minimal.dev) sandbox, packaged as
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
| `minimal-setup` | Get a repo running in a Minimal sandbox: install, `min init`, session creation and activation. |
| `minimal-config` | Author and validate `minimal.toml`: packages, profiles, stacks, upstream pinning, `mip check`. |
| `minimal-networking` | Session networking: the routing proxy, ingress, and reaching the host. Experimental. |
| `minimal-diag` | Diagnose broken sessions and builds: `min bug` support bundles, logs, common failure modes. |

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
(`npm install -g @anthropic-ai/claude-code`); `lint-urls` needs neither.

```
just lint-urls        # liveness-check every docs URL in the skills
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
evals/                eval harness: runner.py, checks.py, cases/, SCHEMA.md
.github/workflows/    pr-evals.yml (PR gate), nightly-evals.yml (nightly tier)
justfile              local dev-loop recipes
```

## Notes

- Skills link the published docs at `minimal.dev` instead of restating them;
  the URL contract lives in [evals/SCHEMA.md](evals/SCHEMA.md).
- `minimal-networking` is experimental: its surface has no public docs (that
  is intentional), so it carries inline knowledge and may change or break
  without notice.

## License

MIT, see [LICENSE](LICENSE).

Note: the optional LLM style judge (`--judge`) uses the Anthropic SDK and
needs `ANTHROPIC_API_KEY`; the default pipeline authenticates the `claude`
CLI alone and never requires it.
