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
from challenges.loader import load_challenge, format_challenge_prompt


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

    lines.append(f"\n**Current focus:** {state.current_focus or '(not set)'}")
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

    if state.actions:
        lines.append("\n**Recent actions:**")
        for a in state.actions[-5:]:  # last 5 actions
            lines.append(f"  [step {a.step}] {a.tool}({a.arguments}) → {a.result_summary[:80]}")

    if state.interventions_applied:
        last = state.interventions_applied[-1]
        lines.append(f"\n**Last intervention:** [{last.type}] at step {last.step} (source: {last.source})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a reverse engineer analyzing a Linux ELF binary.

Your goal is to understand the binary's validation logic and produce a valid input that the binary accepts.

## CRITICAL RULES

1. You can ONLY learn about the binary by calling tools. Do NOT imagine or fabricate tool output.
2. You MUST call exactly ONE tool per turn. Write TOOL: on its own line.
3. You MUST end every response with a ```json state update block.
4. Keep responses SHORT — 2-4 sentences of analysis, then the tool call, then the JSON block. No long explanations.

## Available tools

- file()              : show file type info
- strings()           : extract printable strings from the binary
- run_binary(INPUT)   : run the binary with INPUT as its argument
- python_eval(CODE)   : run a Python snippet

To call a tool, write TOOL: followed by the call on its own line:

TOOL: strings()

You will receive the tool's output in the next message. Base your analysis ONLY on actual tool output.

## Investigation state

You have a shared investigation state (shown at the top of each message).
This is your working memory. Keep it accurate.

If an intervention appears in the state, treat it as a colleague's suggestion.

## Response format

Every response must have this structure:

1. Brief analysis of what you learned (1-3 sentences)
2. Your next tool call:
   TOOL: <tool_call>
3. State update:
```json
{
  "new_observations": [{"content": "what you learned", "source": "tool_name"}],
  "hypothesis_updates": [{"claim": "what you believe", "status": "active", "confidence": "low"}],
  "current_focus": "what you are investigating next",
  "current_understanding": "summary of what you know"
}
```

When you have found a valid input, respond with:
SOLUTION: <the valid input>
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
        # First turn: challenge content + initial state
        challenge = load_challenge(state.challenge_id)
        challenge_text = format_challenge_prompt(challenge)
        content = (
            f"{state_block}\n\n"
            f"---\n"
            f"{challenge_text}\n\n"
            f"Begin your investigation. Start by calling file() or strings() to learn about the binary.\n\n"
            f"Remember: you MUST call exactly one tool per response using TOOL: format. "
            f"Example of a correct response:\n\n"
            f"Let me start by examining what type of binary this is.\n\n"
            f"TOOL: file()\n\n"
            f"```json\n"
            f'{{"new_observations": [], '
            f'"hypothesis_updates": [], '
            f'"current_focus": "determine binary type and architecture", '
            f'"current_understanding": "starting investigation"}}\n'
            f"```"
        )
        return [{"role": "user", "content": content}]

    # Subsequent turns: inject updated state into the latest user message
    last_user = (
        f"{state_block}\n\n---\n"
        f"Continue your investigation. Call exactly ONE tool using TOOL: format. "
        f"End with a ```json state update block."
    )
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
