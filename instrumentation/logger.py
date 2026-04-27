"""
instrumentation/logger.py

JSONL step logger for experiment runs.
One JSON object per step, appended to a file.
"""

import json
import re
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"

# Intervention type classifications
LIGHT_TYPES = {"add_hypothesis", "reject_hypothesis", "mark_observation_important"}
STRONG_TYPES = {"suggest_action", "reprioritize_next_steps"}

# Action-gap heuristic keywords
ACTION_WORDS = re.compile(r"\b(use|run|try|execute|call|invoke|let me|let's|i will|i'll)\b", re.IGNORECASE)


def log_path(challenge: str, variant: str, intervention_mode: str, run_id: str) -> Path:
    """Build the log file path."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR / f"{challenge}_{variant}_{intervention_mode}_{run_id}.jsonl"


def log_step(data: dict, filepath: Path) -> None:
    """Append one JSON line to the log file."""
    with open(filepath, "a") as f:
        f.write(json.dumps(data) + "\n")


def build_step_record(
    *,
    run_id: str,
    challenge: str,
    variant: str,
    use_structured_state: bool,
    intervention_mode: str,
    step: int,
    tool_called: bool,
    tool_name: str | None,
    tool_success: bool,
    intervention_applied: bool,
    intervention_type: str | None,
    response_length: int,
    thinking_length: int,
    thinking_text: str,
    response_text: str,
    tool_output: str | None,
    repeated_tool: bool,
    new_tool_used: bool,
    action_gap: bool,
    solved: bool,
    solution: str | None,
) -> dict:
    """Build a step record dict for logging."""
    return {
        "run_id": run_id,
        "challenge": challenge,
        "variant": variant,
        "use_structured_state": use_structured_state,
        "intervention_mode": intervention_mode,
        "step": step,
        "tool_called": tool_called,
        "tool_name": tool_name,
        "tool_success": tool_success,
        "intervention_applied": intervention_applied,
        "intervention_type": intervention_type,
        "response_length": response_length,
        "thinking_length": thinking_length,
        "thinking_text": thinking_text,
        "response_text": response_text,
        "tool_output": tool_output,
        "repeated_tool": repeated_tool,
        "new_tool_used": new_tool_used,
        "action_gap": action_gap,
        "solved": solved,
        "solution": solution,
    }


def detect_action_gap(response: str, tool_called: bool) -> bool:
    """Heuristic: model describes an action but doesn't execute it."""
    if tool_called:
        return False
    return bool(ACTION_WORDS.search(response))


def filter_interventions(
    scripted: list[dict], mode: str
) -> list[dict]:
    """Filter interventions by mode: 'none' returns [], 'light' keeps light types, 'strong' keeps all."""
    if mode == "none":
        return []
    if mode == "light":
        return [iv for iv in scripted if iv.get("type") in LIGHT_TYPES]
    if mode == "strong":
        return scripted  # strong includes all
    return []
