"""Tests for evals/runner.py. Plain unittest: pytest is not configured
in evals/pyproject.toml.

Run with: uv run --project evals python -m unittest evals.test_runner -v
(or `python3 test_runner.py` from the evals/ directory).
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


MAX_TURNS_EVENT = json.dumps({
    "type": "result", "subtype": "error_max_turns", "is_error": True,
    "num_turns": 11, "errors": ["Reached maximum number of turns (10)"],
})

EXECUTION_ERROR_EVENT = json.dumps({
    "type": "result", "subtype": "error_during_execution", "is_error": True,
    "errors": ["API Error: 529 overloaded"],
})


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        without_skill=False, model="fixture", skip_permissions=False, judge=False
    )


class ResultClassificationTest(unittest.TestCase):
    def test_max_turns_is_a_failed_trial_not_an_infra_error(self) -> None:
        calls: list[int] = []

        def fake_run(command, cwd, **kwargs):
            calls.append(1)
            return subprocess.CompletedProcess(command, 1, MAX_TURNS_EVENT, "")

        with mock.patch.object(runner.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(runner.time, "sleep") as sleep:
            record = runner.run_trial("minimal-config", CASE, _args(), known=[])

        self.assertEqual(len(calls), 1)
        sleep.assert_not_called()
        self.assertEqual(record.get("reason"), "max_turns")
        self.assertNotIn("infra_errors", record)
        self.assertFalse(record["passed"])

    def test_infra_error_detail_records_result_subtype_and_errors(self) -> None:
        def fake_run(command, cwd, **kwargs):
            return subprocess.CompletedProcess(command, 1, EXECUTION_ERROR_EVENT, "")

        with mock.patch.object(runner.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(runner.time, "sleep"):
            record = runner.run_trial("minimal-config", CASE, _args(), known=[])

        self.assertEqual(record.get("reason"), "infra_error")
        self.assertEqual(record.get("infra_errors"), 3)
        detail = record.get("infra_error_detail", "")
        self.assertIn("error_during_execution", detail)
        self.assertIn("API Error: 529 overloaded", detail)


if __name__ == "__main__":
    unittest.main()
