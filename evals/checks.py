"""Check registry for the minimal-skills eval harness.

Implements every check in evals/SCHEMA.md ("Check registry"). Each check is
a function ``(args: dict, result: Result) -> bool``. Checks are pure except
the URL-liveness ones, which GET URLs via requests (redirects followed, 10s
timeout, network errors count as failure). All regexes are compiled with
case-insensitive + multiline flags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

FLAGS = re.IGNORECASE | re.MULTILINE

URL_TIMEOUT_S = 10.0

# https://minimal.dev URLs; trailing sentence punctuation stripped separately.
_MINIMAL_URL_RE = re.compile(r"https://minimal\.dev[^\s<>\"'`)\]}]*", re.IGNORECASE)

# ```lang\n ... ``` fenced blocks and `inline code` spans.
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")

_ACTIVATE_RE = re.compile(r"\bmin\s+session\s+activate\b", re.IGNORECASE)
_UPSTREAM_PIN_RE = re.compile(r"\[upstream\][^\[]*?locked_commit", re.IGNORECASE)
_HIDDEN_FLAG_RE = re.compile(r"--(?:network|ingress)\b", re.IGNORECASE)
# Options routinely sit between a package manager and its install verb
# (`apt-get -y install ripgrep`, `apk --no-cache add jq`), so tolerate them.
# Only option-shaped tokens, never arbitrary text: a command-line comment
# such as `# brew is gone, use min add` must still not match.
_OPTS = r"(?:\s+-{1,2}[^\s]+)*"
_HOST_INSTALLER_RE = re.compile(
    rf"(?:sudo\s+)?\b(?:apt(?:-get)?|apk|dnf|yum|brew)\b{_OPTS}\s+(?:install|add)\b"
    rf"|\bpip3?\b{_OPTS}\s+install\b"
    rf"|\bnpm\b{_OPTS}\s+i(?:nstall)?\s+(?:-g|--global)\b"
    rf"|\bcargo\b{_OPTS}\s+install\b",
    re.IGNORECASE,
)
# Any `mip` invocation is host-only, including option-only forms like
# `mip --help`. The lookbehind keeps the docs slug `.../reference/cli-mip`
# from reading as an invocation; citing the reference is not running it.
_HOST_ONLY_MIN_RE = re.compile(
    r"\bmin\s+(?:session|init|ls|stop|bug|loadout|update)\b|(?<![\w/-])mip\b",
    re.IGNORECASE,
)


@dataclass
class Result:
    """What a single trial produced, as consumed by checks."""

    response_text: str
    events: list[dict]
    workspace: Path


Check = Callable[[dict, "Result"], bool]


# --- shared helpers (also used by runner.py --lint-urls) ---


def extract_minimal_urls(text: str) -> list[str]:
    """All https://minimal.dev URLs in text, deduplicated, order preserved."""
    urls: list[str] = []
    for match in _MINIMAL_URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:!?")
        if url and url not in urls:
            urls.append(url)
    return urls


def url_is_200(url: str) -> bool:
    """GET the URL (redirects followed, 10s timeout); network errors fail.

    A redirect chain landing on an /auth/ page (minimal.dev's login wall in
    front of unpublished sections) counts as dead even though the login page
    itself serves 200: the linked content is not publicly readable, which is
    what this check exists to guarantee.
    """
    try:
        response = requests.get(url, timeout=URL_TIMEOUT_S, allow_redirects=True)
        if "/auth/" in response.url:
            return False
        return response.status_code == 200
    except requests.RequestException:
        return False


def _command_lines(text: str) -> list[str]:
    """Lines from fenced code blocks plus inline backtick command spans."""
    lines: list[str] = []
    for match in _FENCE_RE.finditer(text):
        lines.extend(match.group(1).splitlines())
    remainder = _FENCE_RE.sub("", text)
    for match in _INLINE_CODE_RE.finditer(remainder):
        lines.append(match.group(1))
    return lines


# --- parameterized checks ---


def response_matches(args: dict, result: Result) -> bool:
    return re.search(args["pattern"], result.response_text, FLAGS) is not None


def response_not_matches(args: dict, result: Result) -> bool:
    return re.search(args["pattern"], result.response_text, FLAGS) is None


def workspace_file_exists(args: dict, result: Result) -> bool:
    return (result.workspace / args["path"]).exists()


def workspace_file_matches(args: dict, result: Result) -> bool:
    path = result.workspace / args["path"]
    if not path.is_file():
        return False
    content = path.read_text(errors="replace")
    return re.search(args["pattern"], content, FLAGS) is not None


# --- named (no-arg) checks ---


def docs_urls_valid(args: dict, result: Result) -> bool:
    """Every https://minimal.dev/... URL in the response returns HTTP 200."""
    return all(url_is_200(url) for url in extract_minimal_urls(result.response_text))


def cites_docs_url(args: dict, result: Result) -> bool:
    """Response cites at least one minimal.dev/start/ or minimal.dev/docs/ URL."""
    return re.search(r"minimal\.dev/(?:start|docs)/", result.response_text, FLAGS) is not None


def uses_min_init(args: dict, result: Result) -> bool:
    return re.search(r"\bmin\s+init\b", result.response_text, FLAGS) is not None


def activate_no_prompt(args: dict, result: Result) -> bool:
    """Every `min session activate` in a code block or inline command carries
    --no-prompt on the same command line. Prose mentions outside command
    context are not held to it."""
    for line in _command_lines(result.response_text):
        if _ACTIVATE_RE.search(line) and "--no-prompt" not in line:
            return False
    return True


def pins_upstream(args: dict, result: Result) -> bool:
    """An emitted minimal.toml (workspace file, or shown in the response) has
    an [upstream] section carrying locked_commit."""
    candidates: list[str] = []
    if result.workspace.is_dir():
        for path in sorted(result.workspace.rglob("minimal.toml")):
            try:
                candidates.append(path.read_text(errors="replace"))
            except OSError:
                continue
    candidates.append(result.response_text)
    return any(_UPSTREAM_PIN_RE.search(text) for text in candidates)


def mip_check_suggested(args: dict, result: Result) -> bool:
    # `mip` is Linux-only; in-session `min check` is the equivalent (and the
    # only option on macOS), so either spelling satisfies the directive. The
    # tool name may also be paired ("`mip`/`min` check") or wrapped in
    # backticks, so allow punctuation between the tool and the verb: this
    # check asserts that validation was recommended, not how it was spelled.
    return (
        re.search(
            r"\b(?:mip|min)\b[^\w\n]{0,8}(?:\b(?:mip|min)\b[^\w\n]{0,4})?check\b",
            result.response_text,
            FLAGS,
        )
        is not None
    )


def min_bug_suggested(args: dict, result: Result) -> bool:
    return re.search(r"\bmin\s+bug\b", result.response_text, FLAGS) is not None


def no_hidden_flag_leak(args: dict, result: Result) -> bool:
    """Response does NOT recommend --network or --ingress."""
    return _HIDDEN_FLAG_RE.search(result.response_text) is None


def no_host_package_manager(args: dict, result: Result) -> bool:
    """No command line (fenced block or inline command) invokes a host
    package-manager install: apt/apk/dnf/yum/brew install, system pip
    install, global npm install, or cargo install. Inside a sandbox none of
    these exist, so recommending one is always wrong."""
    return not any(_HOST_INSTALLER_RE.search(line) for line in _command_lines(result.response_text))


def routes_to_sandbox_reference(args: dict, result: Result) -> bool:
    """The response resolves the in-sandbox command surface from a live
    source rather than reciting syntax: it tells the reader to run bare
    `min`, or cites the sandbox-operations reference. The helper's verbs
    change between daemon releases, so routing is the correct answer and
    remembered syntax is not."""
    bare_min = re.search(
        r"\bbare\b[^\n]{0,20}\bmin\b"
        r"|\bmin\b[^\n]{0,60}\b(no|without|zero)\b[^\n]{0,20}\b(arg|argument|subcommand|flag)"
        r"|\brun\b[^\n]{0,20}`?min`?[^\n]{0,20}\b(first|alone|by itself)\b",
        result.response_text,
        FLAGS,
    )
    reference = re.search(r"minimal\.dev/docs/reference/sandbox-operations", result.response_text, FLAGS)
    # Declining to guess is the directed behaviour when no shell is available
    # to check with, and it satisfies the same contract: the agent refuses to
    # emit a verb it has not resolved, and defers to the live command list.
    declines_to_guess = re.search(
        r"\b(shouldn.t|should not|won.t|will not|cannot|can.t|not going to)\b[^\n]{0,60}\bguess\b"
        r"|\bguess(ing)?\b[^\n]{0,40}\b(verb|subcommand|command)\b"
        r"|\bresolve\b[^\n]{0,40}\b(command list|current command|its command|subcommand)",
        result.response_text,
        FLAGS,
    )
    return bool(bare_min or reference or declines_to_guess)


def no_host_only_commands(args: dict, result: Result) -> bool:
    """Response does NOT reach for host-only Minimal commands (`min session`,
    `min init`, `min ls`, `min stop`, `min bug`, `min loadout`, `min update`,
    or any `mip` invocation). Blunt whole-text scan; use it only on cases
    where mentioning a host command is never warranted."""
    return _HOST_ONLY_MIN_RE.search(result.response_text) is None


def correct_proxy_port(args: dict, result: Result) -> bool:
    return re.search(r"\b7654\b", result.response_text, FLAGS) is not None


def host_alias_ip_correct(args: dict, result: Result) -> bool:
    return re.search(r"\b100\.64\.255\.254\b", result.response_text, FLAGS) is not None


CHECK_REGISTRY: dict[str, Check] = {
    # parameterized
    "response_matches": response_matches,
    "response_not_matches": response_not_matches,
    "workspace_file_exists": workspace_file_exists,
    "workspace_file_matches": workspace_file_matches,
    # named
    "docs_urls_valid": docs_urls_valid,
    "cites_docs_url": cites_docs_url,
    "uses_min_init": uses_min_init,
    "activate_no_prompt": activate_no_prompt,
    "pins_upstream": pins_upstream,
    "mip_check_suggested": mip_check_suggested,
    "min_bug_suggested": min_bug_suggested,
    "no_hidden_flag_leak": no_hidden_flag_leak,
    "no_host_package_manager": no_host_package_manager,
    "routes_to_sandbox_reference": routes_to_sandbox_reference,
    "no_host_only_commands": no_host_only_commands,
    "correct_proxy_port": correct_proxy_port,
    "host_alias_ip_correct": host_alias_ip_correct,
}
