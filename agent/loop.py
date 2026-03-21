"""
agent/loop.py

The main agent loop. Both baseline and structured agents run through this.
The only difference between them is the build_prompt_fn they pass in.

LLM calls and tool execution are stubbed out — to be filled in later.
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state.schema import (
    InvestigationState,
    Observation,
    Hypothesis,
    ActionRecord,
    Intervention,
)


# ---------------------------------------------------------------------------
# Stubs — replace these in later files
# ---------------------------------------------------------------------------

def stub_llm_call(prompt: str) -> dict:
    """Fake LLM response: returns a hardcoded agent action."""
    return {
        "thinking": "The file looks like an ELF binary. I should run strings on it first.",
        "tool": "strings",
        "tool_args": {"file": "crackme"},
        "state_update": {
            "new_observation": {
                "content": "Found string 'Enter flag:' and a suspicious hex blob 0x1337beef",
                "source": "strings",
            },
            "new_hypothesis": {
                "claim": "Flag is XOR-encoded with the constant 0x1337beef",
                "confidence": "low",
            },
            "current_understanding": "Binary asks for a flag. Likely XOR-encodes input and compares.",
        },
        "flag_candidate": None,
    }


def stub_execute_tool(tool: str, args: dict) -> str:
    """Fake tool execution: returns a hardcoded result string."""
    return f"[stub] {tool} output for args {args}"


def stub_build_prompt(state: InvestigationState, messages: list[dict]) -> str:
    """Placeholder prompt builder — replaced by baseline.py or structured.py."""
    return f"[stub prompt] step={state.step} challenge={state.challenge_id}"


def stub_check_intervention(step: int) -> Intervention | None:
    """Returns a scripted intervention at step 1, None otherwise."""
    if step == 1:
        return Intervention(
            id="iv-001",
            type="add_hypothesis",
            payload={
                "claim": "The binary may use a simple Caesar shift, not XOR",
                "confidence": "medium",
            },
            step=step,
            source="scripted",
        )
    return None


# ---------------------------------------------------------------------------
# Intervention application (will move to state/intervention.py)
# ---------------------------------------------------------------------------

def apply_intervention(state: InvestigationState, iv: Intervention) -> InvestigationState:
    """Apply a single intervention to the state. Modifies in place."""
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
    # other types handled in state/intervention.py later
    state.interventions_applied.append(iv)
    return state


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(
    challenge_id: str,
    agent_variant: str,
    build_prompt_fn=None,
    max_steps: int = 10,
) -> InvestigationState:

    if build_prompt_fn is None:
        build_prompt_fn = stub_build_prompt

    # --- Initialize ---
    state = InvestigationState(
        challenge_id=challenge_id,
        agent_variant=agent_variant,
    )
    messages: list[dict] = []  # conversation history for baseline agent

    print(f"\n=== Starting run: {challenge_id} [{agent_variant}] ===\n")

    for step in range(1, max_steps + 1):
        state.step = step

        # --- AI TURN ---
        prompt = build_prompt_fn(state, messages)
        response = stub_llm_call(prompt)

        # Apply state update from LLM response
        upd = response.get("state_update", {})

        if "new_observation" in upd:
            obs_data = upd["new_observation"]
            state.observations.append(Observation(
                id=state.next_obs_id(),
                content=obs_data["content"],
                source=obs_data["source"],
                step=step,
            ))

        if "new_hypothesis" in upd:
            hyp_data = upd["new_hypothesis"]
            state.hypotheses.append(Hypothesis(
                id=state.next_hyp_id(),
                claim=hyp_data["claim"],
                status="active",
                confidence=hyp_data.get("confidence", "low"),
                origin="agent",
                step_created=step,
                step_updated=step,
            ))

        if "current_understanding" in upd:
            state.current_understanding = upd["current_understanding"]

        # Record the action
        state.actions.append(ActionRecord(
            step=step,
            tool=response["tool"],
            arguments=response["tool_args"],
            result_summary=stub_execute_tool(response["tool"], response["tool_args"]),
        ))

        # Check for flag
        if response.get("flag_candidate"):
            state.flag_candidate = response["flag_candidate"]
            state.solved = True
            break

        # --- INTERVENTION POINT ---
        print(f"--- State before intervention (step {step}) ---")
        print(json.dumps(state.model_dump(), indent=2))

        intervention = stub_check_intervention(step)
        if intervention:
            print(f"\n>>> Intervention fired: {intervention.type}")
            state = apply_intervention(state, intervention)
            print(f"--- State after intervention (step {step}) ---")
            print(json.dumps(state.model_dump(), indent=2))

        # Append to message history (used by baseline agent)
        messages.append({"role": "assistant", "content": response.get("thinking", "")})

        # Stop after one step for this skeleton
        break

    print(f"\n=== Run complete. Solved: {state.solved} ===\n")
    return state


# ---------------------------------------------------------------------------
# Entry point for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run(
        challenge_id="picoctf_rev01",
        agent_variant="structured",
    )
