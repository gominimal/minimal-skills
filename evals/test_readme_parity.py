"""Tests for evals/readme_parity.py. Plain unittest: pytest is not configured
in evals/pyproject.toml.

Run with: uv run --project evals python -m unittest evals.test_readme_parity -v
(or `python3 evals/test_readme_parity.py` from the evals/ directory).
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import readme_parity  # noqa: E402

SKILL_TEXT = """\
---
name: minimal-setup
description: fixture only
---

# Minimal setup and sessions

## Install

Install with the shell installer (Linux x86_64/aarch64, macOS Apple Silicon):

```shell
curl --proto "=https" --tlsv1.2 -fsSL https://go.minimal.dev/stable | sh
```

For the nightly channel, replace `stable` with `nightly`. Verify with
`min --version`.

## Onboard a project

1. Run `min init` in the repository root. It detects the stack and scaffolds
   `minimal.toml`; pass `-y` to skip the confirmation prompt.
2. Add the team's tools to the existing `packages` list under `[session]`.
3. Run `min session activate --attach` from the repo root to create the
   session and enter its shell.

## Providers on Linux

Not relevant to this fixture.
"""

README_PARITY = """\
Intro text.

### Start in three commands

Run these from the root of a repository that has no `minimal.toml` yet.

```shell
curl --proto "=https" --tlsv1.2 -fsSL https://go.minimal.dev/stable | sh
min init
min session activate --attach
```

Joining a project that already ships a `minimal.toml`? Skip `min init`.
"""

README_FOUR_COMMANDS = """\
Intro text.

### Start in three commands

```shell
curl --proto "=https" --tlsv1.2 -fsSL https://go.minimal.dev/stable | sh
min init
min session activate --attach
min session attach
```
"""

README_NIGHTLY = """\
Intro text.

### Start in three commands

```shell
curl --proto "=https" --tlsv1.2 -fsSL https://go.minimal.dev/nightly | sh
min init
min session activate --attach
```
"""

README_DIGIT_HEADING = README_PARITY.replace("Start in three commands", "Start in 3 commands")

README_TWO_HEADING = """\
Intro text.

### Start in two commands

```shell
curl --proto "=https" --tlsv1.2 -fsSL https://go.minimal.dev/stable | sh
min init
min session activate --attach
```
"""

EXPECTED_COMMANDS = [
    'curl --proto "=https" --tlsv1.2 -fsSL https://go.minimal.dev/stable | sh',
    "min init",
    "min session activate --attach",
]


class ReadmeCommandsTests(unittest.TestCase):
    def test_parity_readme(self):
        self.assertEqual(readme_parity.readme_commands(README_PARITY), EXPECTED_COMMANDS)

    def test_fourth_command_is_included(self):
        commands = readme_parity.readme_commands(README_FOUR_COMMANDS)
        self.assertEqual(len(commands), 4)
        self.assertEqual(commands[3], "min session attach")

    def test_ignores_comments_and_blank_lines(self):
        text = README_PARITY.replace(
            "min init\n", "# a comment, not a command\n\nmin init\n"
        )
        commands = readme_parity.readme_commands(text)
        self.assertEqual(commands, EXPECTED_COMMANDS)

    def test_missing_heading_raises(self):
        with self.assertRaises(ValueError):
            readme_parity.readme_commands("no heading here at all")


class SkillCommandsTests(unittest.TestCase):
    def test_skill_commands_ordered(self):
        self.assertEqual(readme_parity.skill_commands(SKILL_TEXT), EXPECTED_COMMANDS)

    def test_missing_onboard_command_raises(self):
        broken = SKILL_TEXT.replace("`min init`", "min init")
        with self.assertRaises(ValueError):
            readme_parity.skill_commands(broken)

    def test_missing_install_heading_raises(self):
        broken = SKILL_TEXT.replace("## Install", "## Setup")
        with self.assertRaises(ValueError):
            readme_parity.skill_commands(broken)


class CompareTests(unittest.TestCase):
    def test_parity_has_no_diff(self):
        readme = readme_parity.readme_commands(README_PARITY)
        skill = readme_parity.skill_commands(SKILL_TEXT)
        self.assertEqual(readme_parity.compare(readme, skill), [])

    def test_fourth_command_is_flagged(self):
        readme = readme_parity.readme_commands(README_FOUR_COMMANDS)
        skill = readme_parity.skill_commands(SKILL_TEXT)
        diffs = readme_parity.compare(readme, skill)
        self.assertTrue(any(d.startswith("command 4:") for d in diffs))

    def test_nightly_channel_is_flagged(self):
        readme = readme_parity.readme_commands(README_NIGHTLY)
        skill = readme_parity.skill_commands(SKILL_TEXT)
        diffs = readme_parity.compare(readme, skill)
        self.assertTrue(any(d.startswith("command 1:") for d in diffs))
        self.assertFalse(any(d.startswith("command 2:") for d in diffs))
        self.assertFalse(any(d.startswith("command 3:") for d in diffs))


class MainTests(unittest.TestCase):
    def _run_main(self, readme_text: str, skill_text: str = SKILL_TEXT) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            readme_path = Path(tmp) / "README.md"
            skill_path = Path(tmp) / "SKILL.md"
            readme_path.write_text(readme_text)
            skill_path.write_text(skill_text)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = readme_parity.main(
                    ["--readme-file", str(readme_path), "--skill", str(skill_path)]
                )
            return code, stdout.getvalue(), stderr.getvalue()

    def test_parity_exits_zero(self):
        code, out, _ = self._run_main(README_PARITY)
        self.assertEqual(code, 0)
        self.assertIn("agree", out)

    def test_fourth_command_exits_one(self):
        code, out, _ = self._run_main(README_FOUR_COMMANDS)
        self.assertEqual(code, 1)
        self.assertIn("command 4", out)

    def test_nightly_channel_exits_one(self):
        code, out, _ = self._run_main(README_NIGHTLY)
        self.assertEqual(code, 1)
        self.assertIn("command 1", out)

    def test_heading_with_digit_is_parity(self):
        code, _, _ = self._run_main(README_DIGIT_HEADING)
        self.assertEqual(code, 0)

    def test_heading_says_two_exits_one(self):
        code, out, _ = self._run_main(README_TWO_HEADING)
        self.assertEqual(code, 1)
        self.assertIn("three", out)

    def test_missing_readme_file_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "SKILL.md"
            skill_path.write_text(SKILL_TEXT)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = readme_parity.main(
                    [
                        "--readme-file", str(Path(tmp) / "nope.md"),
                        "--skill", str(skill_path),
                    ]
                )
            self.assertEqual(code, 2)

    def test_disallowed_url_is_refused(self):
        with self.assertRaises(ValueError):
            readme_parity.check_url("https://example.com/README.md")


if __name__ == "__main__":
    unittest.main()
