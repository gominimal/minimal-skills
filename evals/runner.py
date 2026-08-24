#!/usr/bin/env python3
"""Eval runner for minimal-skills. Binding contract: evals/SCHEMA.md.

Run with: uv run --project evals evals/runner.py [flags]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
CASES_DIR = EVALS_DIR / "cases"
SKILLS_DIR = REPO_ROOT / "skills"

sys.path.insert(0, str(EVALS_DIR))

import checks as checks_mod  # noqa: E402

DEFAULT_ALLOWED_TOOLS = {
    "text": ["Skill"],
    "functional": ["Skill", "Bash", "Read", "Write", "Edit"],
}
TRIAL_TIMEOUT_S = {"text": 300, "functional": 900}
ASSERT_TIMEOUT_S = 30
# Execution/mutation tools hard-denied in text tier (see run_trial).
EXEC_TOOLS = [
    "Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch",
    "Task", "Agent", "KillShell", "BashOutput",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="runner.py",
        description="minimal-skills eval runner (contract: evals/SCHEMA.md)",
    )
    parser.add_argument(
        "--skill", action="append", metavar="NAME",
        help="skill to run cases for; repeatable; default all skills",
    )
    parser.add_argument(
        "--id", action="append", metavar="CASE_ID", dest="ids",
        help="case id to run; repeatable; default all cases",
    )
    parser.add_argument(
        "--tier", choices=["text", "functional", "all"], default="text",
        help="case tier to run (default: text)",
    )
    parser.add_argument(
        "--suite", choices=["regression", "capability", "all"], default="all",
        help="case suite to run (default: all)",
    )
    parser.add_argument(
        "--trials", type=int, default=1,
        help="trials per case unless the case sets its own (default: 1)",
    )
    parser.add_argument(
        "--retries", type=int, default=2,
        help=(
            "extra attempts for a REGRESSION case that fails, to absorb model "
            "nondeterminism (default: 2). A case passes if any attempt passes; "
            "0 disables. Only failures cost anything: a green suite never retries"
        ),
    )
    parser.add_argument(
        "--without-skill", action="store_true",
        help="obsolescence mode: skills are not installed into the workspace",
    )
    parser.add_argument(
        "--judge", action="store_true",
        help="enable the LLM style judge (advisory; off by default)",
    )
    parser.add_argument(
        "--model", default="sonnet",
        help="model passed to the claude CLI (default: sonnet)",
    )
    parser.add_argument(
        "--skip-permissions", action="store_true",
        help="pass --dangerously-skip-permissions to claude (CI containers only)",
    )
    parser.add_argument("--report", metavar="PATH", help="write the JSON report here")
    parser.add_argument(
        "--summary", metavar="PATH",
        help="write a markdown summary here (CI appends to $GITHUB_STEP_SUMMARY)",
    )
    parser.add_argument(
        "--lint-urls", action="store_true",
        help="no-LLM mode: check every minimal.dev URL in skills/ returns 200",
    )
    return parser.parse_args(argv)


# --- URL lint mode (no API key, never invokes claude) ---


def lint_urls() -> int:
    files = [
        path
        for pattern in ("*/SKILL.md", "*/references/*")
        for path in sorted(SKILLS_DIR.glob(pattern))
        if path.is_file()
    ]
    if not files:
        print("no skill files found")
        return 0
    urls: list[str] = []
    for path in files:
        for url in checks_mod.extract_minimal_urls(path.read_text(errors="replace")):
            if url not in urls:
                urls.append(url)
    if not urls:
        print(f"no minimal.dev URLs found in {len(files)} skill file(s)")
        return 0
    import requests

    failures = 0
    for url in urls:
        try:
            response = requests.get(url, timeout=checks_mod.URL_TIMEOUT_S, allow_redirects=True)
            if "/auth/" in response.url:
                # Auth wall: content not publicly readable (see checks.url_is_200).
                status = "AUTH"
                ok = False
            else:
                status = str(response.status_code)
                ok = response.status_code == 200
        except requests.RequestException as exc:
            status = f"ERR({type(exc).__name__})"
            ok = False
        print(f"{status:>4}  {url}")
        if not ok:
            failures += 1
    print(f"{len(urls) - failures}/{len(urls)} URLs OK")
    return 1 if failures else 0


# --- case discovery ---


def discover_cases(args: argparse.Namespace) -> list[tuple[str, dict]]:
    selected: list[tuple[str, dict]] = []
    if not CASES_DIR.is_dir():
        return selected
    for case_file in sorted(CASES_DIR.glob("*/cases.json")):
        skill = case_file.parent.name
        if args.skill and skill not in args.skill:
            continue
        # --id filters inside the per-file loop below.
        try:
            cases = json.loads(case_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: cannot read {case_file}: {exc}", file=sys.stderr)
            continue
        if not isinstance(cases, list):
            print(f"warning: {case_file} is not a JSON array; skipping", file=sys.stderr)
            continue
        for case in cases:
            if not isinstance(case, dict):
                continue
            tier = case.get("tier", "text")
            suite = case.get("suite", "regression")
            if args.ids and case.get("id") not in args.ids:
                continue
            if args.tier != "all" and tier != args.tier:
                continue
            if args.suite != "all" and suite != args.suite:
                continue
            selected.append((skill, case))
    return selected


def known_skill_names() -> list[str]:
    names: set[str] = set()
    for root in (SKILLS_DIR, CASES_DIR):
        if root.is_dir():
            for child in root.iterdir():
                if child.is_dir() and child.name.startswith("minimal-"):
                    names.add(child.name)
    return sorted(names)


# --- stream-json parsing ---


def _find_tool_uses(obj: object, out: list[dict]) -> None:
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use":
            out.append(obj)
        for value in obj.values():
            _find_tool_uses(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _find_tool_uses(value, out)


def _collect_strings(obj: object, out: list[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            out.append(str(key))
            _collect_strings(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _collect_strings(value, out)


def detect_triggered_skills(events: list[dict], known: list[str]) -> list[str]:
    """minimal-* skills invoked via a Skill tool_use event (liberal match)."""
    triggered: set[str] = set()
    tool_uses: list[dict] = []
    for event in events:
        _find_tool_uses(event, tool_uses)
    for tool_use in tool_uses:
        name = tool_use.get("name", "")
        if name in known:
            triggered.add(name)
            continue
        if name != "Skill":
            continue
        strings: list[str] = []
        _collect_strings(tool_use.get("input", {}), strings)
        for text in strings:
            for skill in known:
                if skill in text:
                    triggered.add(skill)
    return sorted(triggered)


def extract_response_text(events: list[dict]) -> str:
    """The final "result" event's "result" field, else assistant text blocks."""
    result_text = None
    for event in events:
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            result_text = event["result"]
    if result_text is not None:
        return result_text
    parts: list[str] = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    return "\n".join(parts)


def _is_infra_error(returncode: int, events: list[dict]) -> bool:
    """True when the claude invocation itself failed rather than the case:
    nonzero exit with no usable result event, an explicit error result, or a
    run that produced no events at all."""
    result_events = [e for e in events if e.get("type") == "result"]
    if not events:
        return True
    if result_events and any(e.get("is_error") for e in result_events):
        return True
    return returncode != 0 and not result_events


def parse_stream_json(stdout: str) -> list[dict]:
    events: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


# --- trial execution ---


def install_skills(workspace: Path) -> None:
    """Copy ALL skill directories into <workspace>/.claude/skills/."""
    if not SKILLS_DIR.is_dir():
        return
    dest_root = workspace / ".claude" / "skills"
    dest_root.mkdir(parents=True, exist_ok=True)
    for child in sorted(SKILLS_DIR.iterdir()):
        if child.is_dir():
            shutil.copytree(child, dest_root / child.name)


def run_checks(case: dict, result: checks_mod.Result) -> tuple[dict[str, bool], bool]:
    outcomes: dict[str, bool] = {}
    all_ok = True
    for spec in case.get("expected_checks") or []:
        if isinstance(spec, str):
            name, check_args = spec, {}
        else:
            name, check_args = spec.get("name", ""), spec.get("args") or {}
        check = checks_mod.CHECK_REGISTRY.get(name)
        if check is None:
            print(f"    unknown check name: {name!r}", file=sys.stderr)
            ok = False
        else:
            try:
                ok = bool(check(check_args, result))
            except Exception as exc:
                print(f"    check {name} raised {type(exc).__name__}: {exc}", file=sys.stderr)
                ok = False
        key, i = name, 2
        while key in outcomes:
            key = f"{name}#{i}"
            i += 1
        outcomes[key] = ok
        all_ok = all_ok and ok
    return outcomes, all_ok


def run_asserts(case: dict, workspace: Path) -> bool:
    for command in case.get("functional_asserts") or []:
        try:
            completed = subprocess.run(
                command, shell=True, cwd=workspace,
                capture_output=True, text=True, timeout=ASSERT_TIMEOUT_S,
            )
            if completed.returncode != 0:
                return False
        except subprocess.TimeoutExpired:
            return False
    return True


def run_trial(
    skill: str, case: dict, args: argparse.Namespace, known: list[str]
) -> dict:
    tier = case.get("tier", "text")
    allowed_tools = case.get("allowed_tools") or DEFAULT_ALLOWED_TOOLS.get(tier, ["Skill"])
    timeout = TRIAL_TIMEOUT_S.get(tier, TRIAL_TIMEOUT_S["text"])
    workspace = Path(tempfile.mkdtemp(prefix="minimal-skills-eval-"))
    record: dict = {
        "triggered_skills": [],
        "trigger_ok": False,
        "checks": {},
        "asserts_ok": False,
        "passed": False,
        "duration_s": 0.0,
    }
    start = time.monotonic()
    try:
        if not args.without_skill:
            install_skills(workspace)
        # Seed declared project files so "this project" prompts are coherent.
        for rel_path, content in (case.get("workspace_files") or {}).items():
            target = workspace / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        command = [
            "claude", "-p", case["prompt"],
            "--output-format", "stream-json",
            "--verbose",
            "--max-turns", "10",
            "--model", args.model,
            "--allowedTools", ",".join(allowed_tools),
        ]
        # --allowedTools only pre-APPROVES; it does not restrict. Without an
        # explicit deny, a local run inherits the developer's own permission
        # allowlists and a "text" case can execute real commands on their
        # machine (observed: a text case activated a live session on the
        # host). Text tier hard-denies every execution/mutation tool the case
        # did not explicitly allow.
        if tier == "text":
            denied = [t for t in EXEC_TOOLS if t not in allowed_tools]
            if denied:
                command += ["--disallowedTools", ",".join(denied)]
        if args.skip_permissions:
            command.append("--dangerously-skip-permissions")
        # A CLI-level failure (nonzero exit with no result event, or an
        # error result) is INFRA noise: rate limits, auth, transient API
        # errors. It says nothing about the skill, so retry with backoff
        # instead of grading it (observed: a shared-token rate limit turned
        # the tail of a nightly run into ~1s failures recorded as skill
        # regressions).
        events: list[dict] = []
        for attempt, backoff_s in enumerate((0, 15, 45)):
            if backoff_s:
                print(
                    f"  infra error; retrying in {backoff_s}s "
                    f"(attempt {attempt + 1}/3)",
                    file=sys.stderr,
                )
                time.sleep(backoff_s)
            try:
                completed = subprocess.run(
                    command, cwd=workspace, env=os.environ.copy(),
                    capture_output=True, text=True, timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                record["reason"] = "timeout"
                return record
            events = parse_stream_json(completed.stdout or "")
            if not _is_infra_error(completed.returncode, events):
                break
            record["infra_errors"] = record.get("infra_errors", 0) + 1
        else:
            record["reason"] = "infra_error"
            stderr_tail = (completed.stderr or "").strip()[-500:]
            if stderr_tail:
                record["infra_error_detail"] = stderr_tail
            return record

        response_text = extract_response_text(events)
        triggered = detect_triggered_skills(events, known)
        record["triggered_skills"] = triggered
        if case.get("should_trigger", True):
            record["trigger_ok"] = skill in triggered
        else:
            record["trigger_ok"] = not triggered

        # Excerpt kept in the report so failed checks can be diagnosed from
        # evidence instead of re-running the trial.
        record["response_excerpt"] = response_text[:4000]

        result = checks_mod.Result(
            response_text=response_text, events=events, workspace=workspace
        )
        record["checks"], checks_ok = run_checks(case, result)
        record["asserts_ok"] = run_asserts(case, workspace)
        record["passed"] = record["trigger_ok"] and checks_ok and record["asserts_ok"]

        if args.judge:
            import judge as judge_mod

            skill_md_path = SKILLS_DIR / skill / "SKILL.md"
            skill_md = (
                skill_md_path.read_text(errors="replace")
                if skill_md_path.is_file()
                else None
            )
            record["judge"] = judge_mod.judge_style(response_text, skill_md)
        return record
    finally:
        record["duration_s"] = round(time.monotonic() - start, 2)
        shutil.rmtree(workspace, ignore_errors=True)


# --- reporting ---


def case_pass(suite: str, trials: list[dict]) -> bool:
    passed = sum(1 for t in trials if t["passed"])
    if suite == "regression":
        return passed == len(trials)
    return passed * 2 >= len(trials)  # capability: >= 50%


def pass_rate(cases: list[dict]) -> float | None:
    if not cases:
        return None
    return round(sum(1 for c in cases if c["passed"]) / len(cases), 4)


def render_summary(case_reports: list[dict], totals: dict) -> str:
    lines = [
        "# minimal-skills eval summary",
        "",
        "| id | skill | suite | trials | verdict |",
        "|---|---|---|---|---|",
    ]
    for case in case_reports:
        passed = sum(1 for t in case["trials"] if t["passed"])
        verdict = "pass" if case["passed"] else "fail"
        if case.get("flaky"):
            verdict += f" (flaky, attempt {case['attempts']})"
        lines.append(
            f"| {case['id']} | {case['skill']} | {case['suite']} "
            f"| {passed}/{len(case['trials'])} | {verdict} |"
        )
    if not case_reports:
        lines.append("| _no cases matched_ | | | | |")

    flaky = [c["id"] for c in case_reports if c.get("flaky")]
    if flaky:
        lines += [
            "",
            f"**Flaky ({len(flaky)}):** {', '.join(flaky)} — passed only on a "
            "retry. Not a build failure, but each one is a case whose assertion "
            "or prompt is sensitive to model nondeterminism; worth tightening.",
        ]

    def fmt(rate: float | None) -> str:
        return "n/a" if rate is None else f"{rate * 100:.0f}%"

    lines += [
        "",
        f"**Totals:** regression pass rate {fmt(totals['regression_pass_rate'])}, "
        f"capability pass rate {fmt(totals['capability_pass_rate'])}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.lint_urls:
        return lint_urls()

    if shutil.which("claude") is None:
        print("error: claude CLI not found on PATH", file=sys.stderr)
        return 2

    selected = discover_cases(args)
    known = known_skill_names()
    if not selected:
        print("no cases matched the given filters", file=sys.stderr)

    case_reports: list[dict] = []
    for skill, case in selected:
        case_id = case.get("id", "?")
        suite = case.get("suite", "regression")
        tier = case.get("tier", "text")
        trials_n = case.get("trials") or args.trials
        print(
            f"[{case_id}] skill={skill} suite={suite} tier={tier} trials={trials_n}",
            file=sys.stderr,
        )
        # A regression case must pass every trial, so with ~70 such cases even
        # a high per-case success rate makes an all-green run unlikely: the
        # failures compound. Retry a failed regression case instead of running
        # more trials up front, which under that same all-must-pass rule would
        # make flaky cases fail MORE often. Only failures cost anything, and a
        # genuinely broken case fails every attempt.
        max_attempts = 1 + max(0, args.retries) if suite == "regression" else 1
        trials: list[dict] = []
        for attempt in range(1, max_attempts + 1):
            trials = []
            for i in range(trials_n):
                record = run_trial(skill, case, args, known)
                status = "PASS" if record["passed"] else "FAIL"
                if record.get("reason"):
                    status += f" ({record['reason']})"
                label = f"  trial {i + 1}/{trials_n}"
                if attempt > 1:
                    label += f" (attempt {attempt}/{max_attempts})"
                print(f"{label}: {status} in {record['duration_s']}s", file=sys.stderr)
                trials.append(record)
            passed = case_pass(suite, trials)
            if passed or attempt == max_attempts:
                break
            print(
                f"  case {case_id}: failed attempt {attempt}/{max_attempts}, retrying",
                file=sys.stderr,
            )
        # Passing only on a later attempt is a real signal even though it does
        # not fail the build, so surface it rather than burying it.
        flaky = passed and attempt > 1
        case_reports.append({
            "id": case_id,
            "skill": skill,
            "suite": suite,
            "tier": tier,
            "should_trigger": case.get("should_trigger", True),
            "trials": trials,
            "passed": passed,
            "attempts": attempt,
            "flaky": flaky,
        })
        n_pass = sum(1 for t in trials if t["passed"])
        note = f" [FLAKY: passed on attempt {attempt}/{max_attempts}]" if flaky else ""
        print(
            f"  case {case_id}: {'PASS' if passed else 'FAIL'} "
            f"({n_pass}/{len(trials)} trials){note}",
            file=sys.stderr,
        )

    regression = [c for c in case_reports if c["suite"] == "regression"]
    capability = [c for c in case_reports if c["suite"] == "capability"]
    totals = {
        "regression_pass_rate": pass_rate(regression),
        "capability_pass_rate": pass_rate(capability),
    }

    if args.report:
        report = {
            "run": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "args": vars(args),
            },
            "cases": case_reports,
            "totals": totals,
        }
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"report written to {report_path}", file=sys.stderr)

    if args.summary:
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(render_summary(case_reports, totals))
        print(f"summary written to {summary_path}", file=sys.stderr)

    regression_failed = [c for c in regression if not c["passed"]]
    if regression_failed:
        ids = ", ".join(c["id"] for c in regression_failed)
        print(f"FAIL: regression case(s) failed: {ids}", file=sys.stderr)
        return 1
    print("all regression cases passed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
