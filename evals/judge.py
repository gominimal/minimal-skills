"""LLM-as-judge for response STYLE only. Advisory: never gates a trial.

Used by runner.py when --judge is passed. Returns
``{"followed_directives": bool, "concise": bool, "rationale": str}`` on
success, or ``{"error": str}`` on any failure; either way the verdict is
recorded in the report and never affects pass/fail or the exit code.
"""

from __future__ import annotations

JUDGE_MODEL = "claude-sonnet-5"

_SYSTEM = """\
You are a style judge for a Claude Code skill eval. You judge STYLE only,
never technical correctness (other checks cover that). Assess two things:

1. followed_directives: does the response follow the skill's directives
   (recommended commands and flags, linking public docs instead of restating
   them, direct imperative guidance)? If no SKILL.md is provided, judge
   against general Claude Code skill style: direct, actionable, link-first.
2. concise: is the response concise? No filler, no padded restatement of
   documentation, no unnecessary caveats.

Record your verdict with the record_style_verdict tool. Keep the rationale
to one or two sentences.
"""

_VERDICT_TOOL = {
    "name": "record_style_verdict",
    "description": "Record the style verdict for the evaluated assistant response.",
    "input_schema": {
        "type": "object",
        "properties": {
            "followed_directives": {
                "type": "boolean",
                "description": "True if the response follows the skill's directives.",
            },
            "concise": {
                "type": "boolean",
                "description": "True if the response is concise.",
            },
            "rationale": {
                "type": "string",
                "description": "One or two sentences explaining the verdict.",
            },
        },
        "required": ["followed_directives", "concise", "rationale"],
    },
}


def judge_style(
    response_text: str,
    skill_md: str | None = None,
    model: str = JUDGE_MODEL,
) -> dict:
    """Judge the style of a trial response. Never raises."""
    try:
        import anthropic

        client = anthropic.Anthropic()
        parts = []
        if skill_md:
            parts.append(
                "The skill's SKILL.md (the directives the response should follow):"
                "\n\n" + skill_md
            )
        parts.append("The assistant response to judge:\n\n" + (response_text or "(empty)"))
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM,
            tools=[_VERDICT_TOOL],
            tool_choice={"type": "tool", "name": "record_style_verdict"},
            messages=[{"role": "user", "content": "\n\n---\n\n".join(parts)}],
        )
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "record_style_verdict":
                data = dict(block.input)
                return {
                    "followed_directives": bool(data.get("followed_directives", False)),
                    "concise": bool(data.get("concise", False)),
                    "rationale": str(data.get("rationale", "")),
                }
        return {"error": "judge response contained no record_style_verdict tool_use"}
    except Exception as exc:  # advisory: any failure is recorded, never raised
        return {"error": f"{type(exc).__name__}: {exc}"}
