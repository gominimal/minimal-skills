#!/usr/bin/env python3
"""Assert gominimal/minimal's README matches the minimal-setup skill.

The README's "Start in three commands" block and the minimal-setup skill's
install/onboarding steps describe the same three commands in two different
repositories. Nothing keeps them in sync automatically, so this is a static
canary: if either side drifts, this check fails instead of the skill quietly
teaching a stale (or made-up) command.

Stdlib only, mirroring evals/docs_hash.py: this runs in the lint-urls job
with no guarantee of installed dependencies.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_S = 30
DEFAULT_README_URL = (
    "https://raw.githubusercontent.com/gominimal/minimal/main/README.md"
)
# Anchored to the repository, not the caller's working directory, so the
# check behaves the same from `evals/`, the repo root, or CI.
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SKILL_PATH = str(REPO_ROOT / "skills" / "minimal-setup" / "SKILL.md")
# This check's whole claim is "the README on gominimal/minimal main still
# lists these commands". Fetching (or following a redirect to) anything else
# would compare the skill against a document it never actually read.
ALLOWED_URL_PREFIX = "https://raw.githubusercontent.com/gominimal/minimal/"

_HEADING_RE = re.compile(r"^###[ \t]+(Start in \S+ commands)[ \t]*$", re.MULTILINE)
_SHELL_FENCE_RE = re.compile(r"```shell\n(.*?)```", re.DOTALL)
_INSTALL_HEADING_RE = re.compile(r"^##[ \t]+Install[ \t]*$", re.MULTILINE)
_ONBOARD_HEADING_RE = re.compile(r"^##[ \t]+Onboard a project[ \t]*$", re.MULTILINE)
_NEXT_H2_RE = re.compile(r"^##[ \t]+\S", re.MULTILINE)
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
# Order matters: this is also the order the onboarding steps present them in.
_ONBOARD_VERBS = ("min init", "min session activate --attach")


def _normalize(line: str) -> str:
    return " ".join(line.split())


def _fence_lines(block: str) -> list[str]:
    """Non-empty, non-comment lines of a fenced code block, whitespace-normalized."""
    lines = []
    for raw in block.splitlines():
        line = _normalize(raw)
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def readme_commands(text: str) -> list[str]:
    """Commands in the README's first ```shell block under 'Start in ... commands'.

    The heading's stated count is not enforced here (a README that says "two
    commands" while listing three is a drift for main() to report, not a
    reason for this extractor to give up).
    """
    heading_match = _HEADING_RE.search(text)
    if not heading_match:
        raise ValueError(
            "no '### Start in <N> commands' heading found in the README"
        )
    fence_match = _SHELL_FENCE_RE.search(text, heading_match.end())
    if not fence_match:
        raise ValueError(
            f"no ```shell fenced block found after {heading_match.group(1)!r}"
        )
    return _fence_lines(fence_match.group(1))


def skill_commands(text: str) -> list[str]:
    """[installer, "min init", "min session activate --attach"] from SKILL.md."""
    install_match = _INSTALL_HEADING_RE.search(text)
    if not install_match:
        raise ValueError("no '## Install' heading found in SKILL.md")
    fence_match = _SHELL_FENCE_RE.search(text, install_match.end())
    if not fence_match:
        raise ValueError("no ```shell fenced block found under '## Install'")
    installer_lines = _fence_lines(fence_match.group(1))
    if not installer_lines:
        raise ValueError("the ```shell block under '## Install' has no command")
    installer = installer_lines[0]

    onboard_match = _ONBOARD_HEADING_RE.search(text)
    if not onboard_match:
        raise ValueError("no '## Onboard a project' heading found in SKILL.md")
    next_heading = _NEXT_H2_RE.search(text, onboard_match.end())
    section_end = next_heading.start() if next_heading else len(text)
    section = text[onboard_match.end():section_end]

    found: list[str] = []
    for match in _BACKTICK_RE.finditer(section):
        span = _normalize(match.group(1))
        if span in _ONBOARD_VERBS and span not in found:
            found.append(span)
    missing = [verb for verb in _ONBOARD_VERBS if verb not in found]
    if missing:
        raise ValueError(
            "the '## Onboard a project' section is missing backticked "
            "command(s): " + ", ".join(repr(m) for m in missing)
        )
    # The skill's numbered steps fix the order (init, then activate); the
    # prose may mention them in any order, so emit them in _ONBOARD_VERBS
    # order rather than in order of first appearance.
    return [installer, *[verb for verb in _ONBOARD_VERBS if verb in found]]


def compare(readme: list[str], skill: list[str]) -> list[str]:
    """Human-readable diff lines; an empty list means parity."""
    diffs: list[str] = []
    for i in range(max(len(readme), len(skill))):
        r = readme[i] if i < len(readme) else None
        s = skill[i] if i < len(skill) else None
        if r == s:
            continue
        if s is None:
            diffs.append(
                f"command {i + 1}: README has {r!r}, which is not one of the "
                "three commands the minimal-setup skill's install and onboarding steps run"
            )
        elif r is None:
            diffs.append(
                f"command {i + 1}: minimal-setup skill runs {s!r}, missing from the README block"
            )
        else:
            diffs.append(
                f"command {i + 1}: README has {r!r}, minimal-setup skill has {s!r}"
            )
    return diffs


def check_url(url: str) -> str:
    """Return `url` if it addresses a file this check is allowed to fetch."""
    if not url.startswith(ALLOWED_URL_PREFIX):
        raise ValueError(
            f"refusing {url!r}: only {ALLOWED_URL_PREFIX}... URLs are fetched"
        )
    return url


class _BoundedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects only while they stay under ALLOWED_URL_PREFIX.

    Left alone urlopen follows a redirect anywhere, and the fetched bytes
    would silently be some other document while this check keeps reporting
    results against the gominimal/minimal README.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_BoundedRedirectHandler)


def fetch_readme(url: str) -> str:
    request = urllib.request.Request(
        check_url(url), headers={"User-Agent": "minimal-skills-readme-parity"}
    )
    with _OPENER.open(request, timeout=TIMEOUT_S) as response:
        check_url(response.geturl())
        return response.read().decode("utf-8", "replace")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="readme_parity.py",
        description=(
            "Assert the gominimal/minimal README's 'Start in three commands' "
            "block matches the minimal-setup skill."
        ),
    )
    parser.add_argument(
        "--readme-url", default=DEFAULT_README_URL,
        help=f"README URL to fetch (default: {DEFAULT_README_URL})",
    )
    parser.add_argument(
        "--readme-file",
        help="local README.md path instead of --readme-url, for offline use or testing",
    )
    parser.add_argument(
        "--skill", default=DEFAULT_SKILL_PATH,
        help=f"path to the SKILL.md to compare against (default: {DEFAULT_SKILL_PATH})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.readme_file:
            readme_text = Path(args.readme_file).read_text()
        else:
            readme_text = fetch_readme(args.readme_url)
        skill_text = Path(args.skill).read_text()
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        readme_cmds = readme_commands(readme_text)
        skill_cmds = skill_commands(skill_text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    heading = _HEADING_RE.search(readme_text).group(1)  # readme_commands proved this matches
    diffs = compare(readme_cmds, skill_cmds)
    if not re.search(r"\b(three|3)\b", heading.lower()):
        diffs.append(
            f"README heading says {heading!r}, but should state 'three' (or '3')"
        )
    if len(readme_cmds) != 3:
        diffs.append(
            f"README block lists {len(readme_cmds)} command(s); the skill runs three"
        )

    if diffs:
        print("README/minimal-setup command parity check FAILED:")
        for line in diffs:
            print(f"  - {line}")
        return 1

    print(f"README and minimal-setup skill agree on {len(readme_cmds)} commands:")
    for cmd in readme_cmds:
        print(f"  - {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
