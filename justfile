# Local eval loop for minimal-skills. LLM recipes (everything except
# lint-urls) need an authenticated claude CLI on PATH (CLAUDE_CODE_OAUTH_TOKEN in CI)
# (npm install -g @anthropic-ai/claude-code). Runner contract: evals/SCHEMA.md.

# List available recipes.
default:
    @just --list

# Text-tier evals, all skills, 1 trial.
eval:
    uv run --project evals evals/runner.py --tier text --trials 1 --report evals/reports/eval.json

# Text-tier evals for a single skill, 1 trial.
eval-skill skill:
    uv run --project evals evals/runner.py --skill {{skill}} --tier text --trials 1 --report evals/reports/eval-{{skill}}.json

# Fast trigger-accuracy pass (text tier, 1 trial).
triggers:
    uv run --project evals evals/runner.py --tier text --trials 1

# Liveness-check every minimal.dev URL in skills/*/SKILL.md (no LLM, no key).
lint-urls:
    uv run --project evals evals/runner.py --lint-urls

# Functional-tier evals; needs a local Minimal install (`min` on PATH).
functional:
    uv run --project evals evals/runner.py --tier functional --trials 1 --report evals/reports/functional-local.json

# Obsolescence check: text tier with the skills NOT installed.
obsolescence:
    uv run --project evals evals/runner.py --tier text --without-skill --trials 1 --report evals/reports/obsolescence.json

# Open the most recent JSON report.
report:
    open "$(ls -t evals/reports/*.json | head -1)"
