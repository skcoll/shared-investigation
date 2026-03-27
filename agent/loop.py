"""
agent/loop.py

The main agent loop for RE investigation.
Both baseline and structured agents run through this.

Experimental conditions are controlled by two flags:
  - use_structured_state: bool  (determines prompt variant)
  - intervention_mode: "none" | "light" | "strong"

These flags fully determine the experimental condition:
  A: baseline, none     B: baseline, light
  C: structured, none   D: structured, light
  E: structured, strong
"""

import json
import re
import sys
import os
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from state.schema import (
    InvestigationState,
    Observation,
    Hypothesis,
    ActionRecord,
    Intervention,
)
from agent.llm_client import load_config, call as llm_call
from agent.baseline import build_prompt as baseline_build_prompt, SYSTEM_PROMPT as BASELINE_SYSTEM_PROMPT
from agent.structured import build_prompt as structured_build_prompt, SYSTEM_PROMPT as STRUCTURED_SYSTEM_PROMPT
from agent import tools
from instrumentation.logger import (
    log_path, log_step, build_step_record, detect_action_gap, filter_interventions,
)

VARIANT_REGISTRY = {
    "baseline": {
        "build_prompt": baseline_build_prompt,
        "system_prompt": BASELINE_SYSTEM_PROMPT,
    },
    "structured": {
        "build_prompt": structured_build_prompt,
        "system_prompt": STRUCTURED_SYSTEM_PROMPT,
    },
}

CHALLENGES_DIR = Path(__file__).parent.parent / "challenges"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_solution(text: str) -> str | None:
    """Pull SOLUTION: <value> from response text."""
    match = re.search(r"SOLUTION:\s*(.+)", text)
    return match.group(1).strip() if match else None


def _extract_state_update(text: str) -> dict | None:
    """Extract a JSON block from ```json ... ``` fences in response text."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _extract_tool_call(text: str) -> tuple[str, dict] | None:
    """Parse TOOL: name(args) from response text."""
    match = re.search(r"TOOL:\s*(\w+)\((.*?)\)\s*$", text, re.MULTILINE)
    if not match:
        match = re.search(r"TOOL:\s*(\w+)\(([^)]*)\)", text)
    if not match:
        match = re.search(r"TOOL:\s*(\w+)\s*$", text, re.MULTILINE)
        if match:
            return match.group(1), {}
        return None
    name = match.group(1)
    raw_arg = match.group(2).strip()

    dict_match = re.search(r"['\"]input['\"]\s*:\s*['\"]([^'\"]*)['\"]", raw_arg)
    if dict_match:
        raw_arg = dict_match.group(1)

    raw_arg = raw_arg.strip("'\"")

    if name == "file":
        return name, {"path": raw_arg or ""}
    if name == "strings":
        return name, {"path": raw_arg or ""}
    if name == "run_binary":
        return name, {"input": raw_arg}
    if name == "python_eval":
        return name, {"code": raw_arg}
    return name, {"raw": raw_arg}


# ---------------------------------------------------------------------------
# Intervention logic
# ---------------------------------------------------------------------------

def apply_intervention(state: InvestigationState, iv: Intervention) -> InvestigationState:
    """Apply a single intervention to the state."""
    if iv.type == "add_hypothesis":
        state.hypotheses.append(Hypothesis(
            id=state.next_hyp_id(),
            claim=iv.payload["claim"],
            status="active",
            confidence=iv.payload.get("confidence", "medium"),
            origin="intervention",
            step_created=state.step,
            step_updated=state.step,
        ))
    if iv.type == "reject_hypothesis":
        hyp = state.get_hypothesis(iv.payload.get("id", ""))
        if hyp:
            hyp.status = "refuted"
            hyp.step_updated = state.step
    if iv.type == "mark_observation_important":
        obs = state.get_observation(iv.payload.get("id", ""))
        if obs:
            obs.important = True
    state.interventions_applied.append(iv)
    return state


def load_interventions(challenge_id: str) -> list[dict]:
    """Load scripted interventions from challenge dir if they exist."""
    iv_path = CHALLENGES_DIR / challenge_id / "interventions.json"
    if iv_path.exists():
        return json.loads(iv_path.read_text())
    return []


def check_intervention(step: int, scripted: list[dict]) -> Intervention | None:
    """Check if any scripted intervention fires at this step."""
    for iv in scripted:
        if iv.get("step") == step:
            return Intervention(
                id=iv.get("id", f"iv-{step:03d}"),
                type=iv["type"],
                payload=iv["payload"],
                step=step,
                source="scripted",
            )
    return None


# ---------------------------------------------------------------------------
# State update from JSON block
# ---------------------------------------------------------------------------

def apply_state_update(state: InvestigationState, upd: dict, step: int) -> None:
    """Apply parsed JSON state update to the investigation state."""
    for obs_data in upd.get("new_observations", []):
        if isinstance(obs_data, str):
            content, source = obs_data, "agent"
        else:
            content = obs_data.get("content", str(obs_data))
            source = obs_data.get("source", "agent")
        state.observations.append(Observation(
            id=state.next_obs_id(), content=content, source=source, step=step,
        ))

    for hyp_data in upd.get("hypothesis_updates", []):
        if isinstance(hyp_data, str):
            state.hypotheses.append(Hypothesis(
                id=state.next_hyp_id(), claim=hyp_data,
                status="active", confidence="low", origin="agent",
                step_created=step, step_updated=step,
            ))
            continue
        existing = state.get_hypothesis(hyp_data.get("id", "")) if "id" in hyp_data else None
        if existing:
            existing.claim = hyp_data.get("claim", existing.claim)
            existing.status = hyp_data.get("status", existing.status)
            existing.confidence = hyp_data.get("confidence", existing.confidence)
            existing.step_updated = step
        else:
            state.hypotheses.append(Hypothesis(
                id=state.next_hyp_id(),
                claim=hyp_data.get("claim", str(hyp_data)),
                status=hyp_data.get("status", "active"),
                confidence=hyp_data.get("confidence", "low"),
                origin="agent", step_created=step, step_updated=step,
            ))

    if "current_focus" in upd:
        state.current_focus = upd["current_focus"]
    if "current_understanding" in upd:
        state.current_understanding = upd["current_understanding"]


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(
    challenge_id: str,
    use_structured_state: bool = True,
    intervention_mode: str = "none",
    config: dict | None = None,
    max_steps: int = 10,
    run_id: str | None = None,
) -> InvestigationState:

    if config is None:
        config = load_config()
    if run_id is None:
        run_id = uuid.uuid4().hex[:8]

    # Resolve variant from flag
    variant_name = "structured" if use_structured_state else "baseline"
    variant = VARIANT_REGISTRY[variant_name]
    build_prompt_fn = variant["build_prompt"]
    system_prompt = variant["system_prompt"]

    # Challenge dir for tool execution
    challenge_dir = str(CHALLENGES_DIR / challenge_id)

    # Load and filter interventions
    all_interventions = load_interventions(challenge_id)
    scripted_interventions = filter_interventions(all_interventions, intervention_mode)

    # Set up logging
    logfile = log_path(challenge_id, variant_name, intervention_mode, run_id)

    # Initialize state
    state = InvestigationState(
        challenge_id=challenge_id,
        agent_variant=variant_name,
    )
    messages: list[dict] = []

    # Tracking for derived metrics
    last_tool_name: str | None = None
    tools_used: set[str] = set()

    condition = f"{variant_name}/{intervention_mode}"
    print(f"\n=== Run {run_id}: {challenge_id} [{condition}] ===\n")

    for step in range(1, max_steps + 1):
        state.step = step

        # 1. Build prompt
        prompt_messages = build_prompt_fn(state, messages)

        # 2. Call LLM
        llm_response = llm_call(prompt_messages, config=config, system=system_prompt)

        print(f"\n[step {step}] thinking ({len(llm_response.thinking)} chars)")
        if llm_response.thinking:
            print(f"  {llm_response.thinking[:200]}...")
        print(f"[step {step}] response ({len(llm_response.response)} chars)")
        print(f"  {llm_response.response[:300]}...")

        # 3. Parse tool request
        tool_call = _extract_tool_call(llm_response.response)
        tool_output = None
        tool_called = False
        tool_name = None
        tool_success = False

        if tool_call:
            tool_name, tool_args = tool_call
            tool_called = True
            print(f"[step {step}] TOOL: {tool_name}({tool_args})")
            tool_output = tools.execute(tool_name, tool_args, challenge_dir)
            tool_success = not tool_output.startswith("[error]")
            print(f"[step {step}] RESULT: {tool_output[:200]}...")

            state.actions.append(ActionRecord(
                step=step, tool=tool_name, arguments=tool_args,
                result_summary=tool_output[:200],
            ))

        # 4. Parse state update (structured agent only)
        upd = _extract_state_update(llm_response.response)
        if upd:
            apply_state_update(state, upd, step)

        # 5. Check for solution
        solved_this_step = False
        solution = _extract_solution(llm_response.response)
        if solution:
            state.solution_candidate = solution
            verify = tools.execute("run_binary", {"input": solution}, challenge_dir)
            print(f"\n>>> SOLUTION proposed: {solution}")
            print(f">>> Verification: {verify}")
            if "Good" in verify or "success" in verify.lower() or "correct" in verify.lower():
                state.solved = True
                solved_this_step = True

        # Auto-detect: if run_binary returned success
        if not solved_this_step and tool_output and tool_call and tool_call[0] == "run_binary":
            if "Good" in tool_output or "success" in tool_output.lower():
                found_input = tool_call[1].get("input", "")
                if found_input:
                    state.solution_candidate = found_input
                    state.solved = True
                    solved_this_step = True
                    print(f"\n>>> AUTO-SOLVED: binary accepted input '{found_input}'")

        # 6. Intervention point
        intervention_applied = False
        intervention_type = None
        intervention = check_intervention(step, scripted_interventions)
        if intervention:
            intervention_applied = True
            intervention_type = intervention.type
            print(f"\n>>> Intervention fired: {intervention.type} — {intervention.payload}")
            state = apply_intervention(state, intervention)

        # 7. Compute derived metrics and log
        repeated_tool = (tool_name is not None and tool_name == last_tool_name)
        new_tool = (tool_name is not None and tool_name not in tools_used)
        action_gap = detect_action_gap(llm_response.response, tool_called)

        if tool_name:
            last_tool_name = tool_name
            tools_used.add(tool_name)

        record = build_step_record(
            run_id=run_id,
            challenge=challenge_id,
            variant=variant_name,
            use_structured_state=use_structured_state,
            intervention_mode=intervention_mode,
            step=step,
            tool_called=tool_called,
            tool_name=tool_name,
            tool_success=tool_success,
            intervention_applied=intervention_applied,
            intervention_type=intervention_type,
            response_length=len(llm_response.response),
            thinking_length=len(llm_response.thinking),
            repeated_tool=repeated_tool,
            new_tool_used=new_tool,
            action_gap=action_gap,
            solved=state.solved,
            solution=state.solution_candidate,
        )
        log_step(record, logfile)

        if solved_this_step:
            break

        # 8. Build history for next turn
        messages.append({"role": "assistant", "content": llm_response.response})
        if tool_output is not None:
            result_msg = f"Tool result:\n{tool_output}"
            if tool_call and tool_call[0] == "run_binary" and ("Good" in tool_output or "success" in tool_output.lower()):
                input_used = tool_call[1].get("input", "")
                result_msg += (
                    f"\n\nThe binary ACCEPTED this input: {input_used}\n"
                    f"If this is a valid serial/key, declare it with: SOLUTION: {input_used}"
                )
            messages.append({"role": "user", "content": result_msg})
        else:
            messages.append({"role": "user", "content":
                "You did not call a tool. You MUST call exactly one tool per turn. "
                "Use TOOL: on its own line. Available tools: "
                "file(), strings(), run_binary(INPUT), python_eval(CODE)"
            })

        # Print state summary
        print(f"[step {step}] state: {len(state.observations)} obs, "
              f"{len(state.hypotheses)} hyp, {len(state.actions)} actions, "
              f"focus='{state.current_focus[:50]}'")

    print(f"\n=== Run {run_id} complete. Solved: {state.solved} ===")
    if state.solution_candidate:
        print(f"Solution: {state.solution_candidate}")
    print(f"Log: {logfile}")
    print()
    return state


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run RE investigation agent")
    parser.add_argument("--config", default=None, help="Path to LLM config file")
    parser.add_argument("--challenge", default="yurisimplekeygen")
    parser.add_argument("--structured", action="store_true", default=False,
                        help="Enable structured state (default: baseline)")
    parser.add_argument("--interventions", default="none",
                        choices=["none", "light", "strong"],
                        help="Intervention mode")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--run-id", default=None, help="Run ID (auto-generated if omitted)")

    # Backwards compat: --variant still works
    parser.add_argument("--variant", default=None, choices=["baseline", "structured"],
                        help="(deprecated) Use --structured flag instead")
    args = parser.parse_args()

    # Handle backwards compat
    use_structured = args.structured
    if args.variant == "structured":
        use_structured = True
    elif args.variant == "baseline":
        use_structured = False

    config = load_config(args.config) if args.config else load_config()
    print(f"Config: {config}")
    print(f"Condition: {'structured' if use_structured else 'baseline'} / {args.interventions}")

    run(
        challenge_id=args.challenge,
        use_structured_state=use_structured,
        intervention_mode=args.interventions,
        config=config,
        max_steps=args.steps,
        run_id=args.run_id,
    )
