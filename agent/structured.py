"""
agent/structured.py

Structured agent: the current InvestigationState is serialized and injected
into every prompt. The model is also asked to emit an update_investigation_state
tool call each turn to keep the state current.

The LLM sees:
  - a system prompt describing the task, tools, and state schema
  - the current investigation state rendered as readable text
  - the conversation history

This is the experimental condition. Comparing its reasoning trace against
baseline directly tests whether visible structured state changes behaviour.
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state.schema import InvestigationState


# ---------------------------------------------------------------------------
# Tool schema: update_investigation_state
# This is passed to the LLM so it knows how to emit structured state updates.
# ---------------------------------------------------------------------------

UPDATE_STATE_TOOL = {
    "name": "update_investigation_state",
    "description": (
        "Update the investigation state after each analysis step. "
        "Call this once per turn alongside your analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "new_observations": {
                "type": "array",
                "description": "New things observed this turn.",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "source":  {"type": "string"},
                    },
                    "required": ["content", "source"],
                },
            },
            "hypothesis_updates": {
                "type": "array",
                "description": "Add a new hypothesis or update an existing one.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id":         {"type": "string",
                                       "description": "Existing hypothesis ID to update, or omit to create new."},
                        "claim":      {"type": "string"},
                        "status":     {"type": "string", "enum": ["active", "supported", "refuted"]},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["claim", "status", "confidence"],
                },
            },
            "new_next_steps": {
                "type": "array",
                "description": "Ordered list of next steps to investigate (highest priority first).",
                "items": {"type": "string"},
            },
            "current_understanding": {
                "type": "string",
                "description": "Plain-language summary of current understanding of the challenge.",
            },
        },
        "required": [],
    },
}


# ---------------------------------------------------------------------------
# State renderer
# Converts InvestigationState into readable text for the prompt.
# Intentionally human-readable, not raw JSON.
# ---------------------------------------------------------------------------

def render_state(state: InvestigationState) -> str:
    lines = ["## Current Investigation State"]

    lines.append(f"\n**Understanding:** {state.current_understanding or '(none yet)'}")

    if state.observations:
        lines.append("\n**Observations:**")
        for o in state.observations:
            tag = " [IMPORTANT]" if o.important else ""
            lines.append(f"  [{o.id}] ({o.source}){tag} {o.content}")
    else:
        lines.append("\n**Observations:** (none yet)")

    if state.hypotheses:
        lines.append("\n**Hypotheses:**")
        for h in state.hypotheses:
            origin = " [from intervention]" if h.origin == "intervention" else ""
            lines.append(f"  [{h.id}] [{h.status.upper()}] [{h.confidence}]{origin} {h.claim}")
    else:
        lines.append("\n**Hypotheses:** (none yet)")

    if state.next_steps:
        lines.append("\n**Next steps (priority order):**")
        for i, step in enumerate(state.next_steps, 1):
            lines.append(f"  {i}. {step}")

    if state.interventions_applied:
        last = state.interventions_applied[-1]
        lines.append(f"\n**Last intervention:** [{last.type}] at step {last.step} (source: {last.source})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert CTF analyst specialising in reverse engineering and cryptography.

Your goal is to analyse the given challenge and find the flag.

## Available tools
- strings(file)            : extract printable strings from a file
- hexdump(file, offset, n) : show n bytes of a file as hex starting at offset
- run_command(cmd)         : run a shell command and return stdout
- python_eval(code)        : execute a Python snippet and return the result

You also have access to a shared investigation state (shown at the top of each
message). After every turn, call update_investigation_state to record what you
observed and what you now believe. This state is your working memory — keep it
accurate and up to date.

If an intervention has been applied (visible in the state), treat it as a
colleague's input: consider it seriously, but you may disagree if the evidence
warrants it.

## How to respond
Think step by step. At each turn:
1. Read the current investigation state.
2. Describe what you observe and what it means.
3. Update your hypotheses based on new evidence.
4. Choose one analysis tool to call next and explain why.
5. Call update_investigation_state with your updates.

If you believe you have found the flag, respond with:
FLAG: <your answer>

Be concise. One analysis tool call per turn.
"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(state: InvestigationState, messages: list[dict]) -> list[dict]:
    """
    Return the messages array to send to the LLM.

    Structured: the rendered investigation state is prepended to every user
    message so the model always sees the current state at the top of its context.
    """
    state_block = render_state(state)

    if not messages:
        # First turn: challenge description + initial state
        content = (
            f"{state_block}\n\n"
            f"---\n"
            f"Challenge: {state.challenge_id}\n\n"
            f"Begin your analysis."
        )
        return [{"role": "user", "content": content}]

    # Subsequent turns: inject updated state into the latest user message
    last_user = f"{state_block}\n\n---\nContinue your analysis."
    return list(messages) + [{"role": "user", "content": last_user}]


# ---------------------------------------------------------------------------
# Manual test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from state.schema import Observation, Hypothesis, Intervention
    from agent.llm_client import call as llm_call

    # Build a state with some content so the render is non-trivial
    state = InvestigationState(challenge_id="picoctf_rev01", agent_variant="structured")
    state.observations.append(Observation(
        id="obs-001", content="64-bit ELF, not stripped",
        source="file", step=1,
    ))
    state.hypotheses.append(Hypothesis(
        id="hyp-001",
        claim="Binary does a direct string comparison",
        status="active", confidence="low",
        origin="agent", step_created=1, step_updated=1,
    ))
    state.hypotheses.append(Hypothesis(
        id="hyp-002",
        claim="Flag may be XOR-encoded",
        status="active", confidence="medium",
        origin="intervention", step_created=1, step_updated=1,
    ))
    state.current_understanding = "Early stage — binary identified, no flag logic found yet."
    state.next_steps = ["Disassemble main()", "Look for comparison functions"]

    messages = []
    built = build_prompt(state, messages)

    print("=== Messages sent to LLM ===")
    for msg in built:
        print(f"\n[{msg['role']}]\n{msg['content']}")

    print("\n=== LLM response (stub) ===")
    result = llm_call(
        built,
        config={"provider": "stub"},
        system=SYSTEM_PROMPT,
        tools=[UPDATE_STATE_TOOL],
    )
    print(f"thinking : {result.thinking}")
    print(f"response : {result.response}")
    print(f"tool_call: {result.tool_call}")
