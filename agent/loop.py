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
from agent.llm_client import load_config, call as llm_call, LLMResponse
from agent.baseline import build_prompt as baseline_build_prompt, SYSTEM_PROMPT as BASELINE_SYSTEM_PROMPT
from agent.structured import build_prompt as structured_build_prompt, SYSTEM_PROMPT as STRUCTURED_SYSTEM_PROMPT

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


def stub_build_prompt(state: InvestigationState, messages: list[dict]) -> list[dict]:
    """Placeholder prompt builder — replaced by baseline.py or structured.py."""
    return [{"role": "user", "content": f"[stub prompt] step={state.step} challenge={state.challenge_id}"}]


def _extract_flag(text: str) -> str | None:
    """Pull FLAG: <value> from response text, if present."""
    import re
    match = re.search(r"FLAG:\s*(.+)", text)
    return match.group(1).strip() if match else None


def _extract_state_update(text: str) -> dict | None:
    """Extract a JSON block from ```json ... ``` fences in response text."""
    import re
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


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
    config: dict | None = None,
    build_prompt_fn=None,
    max_steps: int = 10,
) -> InvestigationState:

    if config is None:
        config = load_config()

    # Resolve variant to get build_prompt, system_prompt, and tools
    variant = VARIANT_REGISTRY.get(agent_variant)
    if build_prompt_fn is None:
        if variant:
            build_prompt_fn = variant["build_prompt"]
        else:
            build_prompt_fn = stub_build_prompt

    system_prompt = variant["system_prompt"] if variant else ""

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
        prompt_messages = build_prompt_fn(state, messages)
        llm_response = llm_call(
            prompt_messages,
            config=config,
            system=system_prompt,
        )

        print(f"[step {step}] thinking: {llm_response.thinking[:120]}...")
        print(f"[step {step}] response: {llm_response.response[:120]}...")

        # Apply state update from JSON block in response (structured agent)
        upd = _extract_state_update(llm_response.response)
        if upd:
            for obs_data in upd.get("new_observations", []):
                state.observations.append(Observation(
                    id=state.next_obs_id(),
                    content=obs_data["content"],
                    source=obs_data.get("source", "agent"),
                    step=step,
                ))

            for hyp_data in upd.get("hypothesis_updates", []):
                existing = state.get_hypothesis(hyp_data.get("id", "")) if "id" in hyp_data else None
                if existing:
                    existing.claim = hyp_data.get("claim", existing.claim)
                    existing.status = hyp_data.get("status", existing.status)
                    existing.confidence = hyp_data.get("confidence", existing.confidence)
                    existing.step_updated = step
                else:
                    state.hypotheses.append(Hypothesis(
                        id=state.next_hyp_id(),
                        claim=hyp_data["claim"],
                        status=hyp_data.get("status", "active"),
                        confidence=hyp_data.get("confidence", "low"),
                        origin="agent",
                        step_created=step,
                        step_updated=step,
                    ))

            if "new_next_steps" in upd:
                state.next_steps = upd["new_next_steps"]

            if "current_understanding" in upd:
                state.current_understanding = upd["current_understanding"]

        # Record the action (tool call from the analysis tools, if any)
        if llm_response.tool_call:
            tc = llm_response.tool_call
            state.actions.append(ActionRecord(
                step=step,
                tool=tc["name"],
                arguments=tc.get("arguments", {}),
                result_summary=stub_execute_tool(tc["name"], tc.get("arguments", {})),
            ))

        # Check for flag in response text
        flag_match = _extract_flag(llm_response.response)
        if flag_match:
            state.flag_candidate = flag_match
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
        messages.append({"role": "assistant", "content": llm_response.response})

    print(f"\n=== Run complete. Solved: {state.solved} ===\n")
    return state


# ---------------------------------------------------------------------------
# Entry point for manual testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None, help="Path to LLM config file (default: llm.config)")
    parser.add_argument("--challenge", default="picoCTF2019_vaultdoor3")
    parser.add_argument("--variant", default="structured", choices=["baseline", "structured"])
    parser.add_argument("--steps", type=int, default=10)
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    print(f"Loaded config: {config}")
    run(
        challenge_id=args.challenge,
        agent_variant=args.variant,
        config=config,
        max_steps=args.steps,
    )
