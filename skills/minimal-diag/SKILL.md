---
name: minimal-diag
description: Use when Minimal itself is broken or misbehaving and the user wants to report a bug or collect diagnostics, e.g. Minimal is broken, a min session won't start, the minimald daemon is unreachable, or a VM boot hangs, and the user mentions Minimal. Do not use for general debugging of the user's own application or for bug reports about non-Minimal software.
---

# minimal-diag

This skill covers exactly one command: `min bug`, Minimal's diagnostic-bundle
collector.

## When to run it

Run `min bug` for any hard-to-explain Minimal failure, before filing a report:
sessions that won't start, VM boots that hang, an unreachable daemon, or any
broken state you cannot explain. Collect the bundle first, then report.

## Invocation

Run `min bug` in the project directory. It is a host command and does not
exist inside a sandbox; from a session, have the user run it on the host
(minimal-sandbox skill). It writes
`minimal-diag-<timestamp>.tar.zst` to the current directory. Flags:

- `--output <path>` (or `-o`): write the bundle to a specific path instead.
- `--no-guest`: skip contacting daemons and collect host-side state only.
  Always pass this when the VM or daemon is wedged, so collection cannot
  hang on it.
- `--guest-timeout-secs <N>`: bound each provider's daemon-bundle download
  (default 60).
- `--log-tail-bytes <N>`: capture more of each log file, counted from the
  end. Raise it when the incident is older than the default tail covers.

## Always safe to run

`min bug` works even when no daemon is running and never starts one, and it
mutates no state. Run it on any broken install; a failed collector becomes an
entry in the bundle's `manifest.json`, not a failed run.

## What is in the bundle, and privacy

The bundle contains host system facts, log tails, redacted config, state
listings, and a `manifest.json` of any collector that failed. Reassure users
before they share it: secret-shaped values (env vars, tokens) are redacted,
and session/project file contents are never included, only name/size
listings.

## Reporting

Tell users to attach the bundle when reporting the issue to the Minimal dev
team. Full command reference: https://minimal.dev/docs/reference/cli-min

## Out of scope

Do not root-cause the failure from this skill; it only collects diagnostics.
For deeper setup and session troubleshooting, use the minimal-setup skill.
