#!/usr/bin/env python3
"""Hash the prose of a minimal.dev docs page, ignoring site chrome.

The drift canary exists to notice when a page the skills cite says something
different. It previously hashed the whole HTTP response, which also covers
Astro's per-build asset fingerprints (`_astro/HtmlDocument.<hash>.css`).
Those rotate on every site deploy, so an unrelated deploy marked all nine
tracked pages as drifted at once and the canary sat red for days — which is
how a canary stops being read.

Stdlib only: this runs in a job with no Python dependencies installed.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import urllib.request

TIMEOUT_S = 30
# A tracked reference page has real prose. Anything shorter means the
# extraction broke (markup changed, error page, empty render) and a hash of
# it would be a silent false negative — the canary would go quiet exactly
# when it should shout.
MIN_TEXT_LEN = 500

_MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)
_DROP_RE = re.compile(r"<(script|style|svg|noscript)\b.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def extract_text(page: str, url: str) -> str:
    match = _MAIN_RE.search(page)
    if not match:
        raise ValueError(f"no <main> element found at {url}")
    body = _DROP_RE.sub(" ", match.group(1))
    text = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", body))).strip()
    if len(text) < MIN_TEXT_LEN:
        raise ValueError(
            f"extracted only {len(text)} chars of text at {url}; "
            "the page markup probably changed — fix the extractor rather "
            "than trusting this hash"
        )
    return text


def hash_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "minimal-skills-docs-drift"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        page = response.read().decode("utf-8", "replace")
    return hashlib.sha256(extract_text(page, url).encode("utf-8")).hexdigest()


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: docs_hash.py URL [URL ...]", file=sys.stderr)
        return 2
    out: dict[str, str] = {}
    for url in argv:
        try:
            out[url] = hash_url(url)
        except Exception as exc:  # noqa: BLE001 - report and fail, never hash junk
            print(f"error: {url}: {exc}", file=sys.stderr)
            return 1
    json.dump(out, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
