"""Tests for evals/runner.py. Plain unittest: pytest is not configured
in evals/pyproject.toml.

Run with: uv run --project evals python -m unittest evals.test_runner -v
(or `python3 evals/test_runner.py` from the evals/ directory).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runner  # noqa: E402

SEEDED_TOML = '[session]\npackages = ["base"]\n'

CASE = {
    "id": "fixture-001",
    "prompt": "Define a test task in minimal.toml.",
    "allowed_tools": ["Skill", "Read", "Write", "Edit"],
    "expected_checks": [],
    "workspace_files": {"minimal.toml": SEEDED_TOML},
}

RESULT_EVENT = json.dumps({"type": "result", "is_error": False, "result": "done"})


class InfraRetryWorkspaceTest(unittest.TestCase):
    def test_infra_retry_starts_from_freshly_seeded_workspace(self) -> None:
        seen: list[str] = []

        def fake_run(command, cwd, **kwargs):
            toml = Path(cwd) / "minimal.toml"
            seen.append(toml.read_text())
            if len(seen) == 1:
                # Edit the workspace, then die the way an infra error does:
                # nonzero exit and no result event.
                toml.write_text(toml.read_text() + "\n[tasks.test]\nexec = \"x\"\n")
                return subprocess.CompletedProcess(command, 1, "", "rate limited")
            return subprocess.CompletedProcess(command, 0, RESULT_EVENT, "")

        args = argparse.Namespace(
            without_skill=False, model="fixture", skip_permissions=False, judge=False
        )
        with mock.patch.object(runner.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(runner.time, "sleep"):
            record = runner.run_trial("minimal-config", CASE, args, known=[])

        self.assertEqual(record.get("infra_errors"), 1)
        self.assertNotIn("reason", record)
        self.assertEqual(seen, [SEEDED_TOML, SEEDED_TOML])


if __name__ == "__main__":
    unittest.main()
