"""
agent/baseline.py

Baseline agent: history-only prompt, no state injection.

The LLM sees:
  - a system prompt describing the task and available tools
  - the full conversation history

The InvestigationState exists in the loop and is updated from the LLM's
response, but it is NEVER shown to the model. This is the control condition.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state.schema import InvestigationState
from challenges.loader import load_challenge, format_challenge_prompt


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a reverse engineer analyzing a Linux ELF binary.

Your goal is to understand the binary's validation logic and produce a valid input that the binary accepts.

## CRITICAL RULES

1. You can ONLY learn about the binary by calling tools. Do NOT imagine or fabricate tool output.
2. You MUST call exactly ONE tool per turn. Write TOOL: on its own line.
3. Keep responses SHORT — 2-4 sentences of analysis, then the tool call. No long explanations.

## Available tools

- file()              : show file type info
- strings()           : extract printable strings from the binary
- run_binary(INPUT)   : run the binary with INPUT as its argument
- python_eval(CODE)   : run a Python snippet

To call a tool, write TOOL: followed by the call on its own line:

TOOL: strings()

You will receive the tool's output in the next message. Base your analysis ONLY on actual tool output.

## Response format

Every response must have:
1. Brief analysis of what you learned (1-3 sentences)
2. Your next tool call on its own line:
   TOOL: <tool_call>

When you have found a valid input, respond with:
SOLUTION: <the valid input>
"""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(state: InvestigationState, messages: list[dict]) -> list[dict]:
    """
    Return the messages array to send to the LLM.

    Baseline: system prompt + conversation history only.
    The state object is intentionally ignored here — the model has no
    visibility into structured state.

    The challenge description is injected once as the first user message
    if the history is empty.
    """
    if not messages:
        # First turn: seed the conversation with the challenge content
        challenge = load_challenge(state.challenge_id)
        challenge_text = format_challenge_prompt(challenge)
        return [
            {"role": "user", "content": (
                f"{challenge_text}\n\n"
                f"Begin your investigation. Start by calling file() or strings() to learn about the binary.\n\n"
                f"Remember: call exactly one tool per response using TOOL: format. Example:\n\n"
                f"TOOL: file()"
            )},
        ]

    return list(messages)  # return history as-is


# ---------------------------------------------------------------------------
# Manual test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from agent.llm_client import call as llm_call

    state = InvestigationState(challenge_id="picoctf_rev01", agent_variant="baseline")
    messages = []

    built = build_prompt(state, messages)
    print("=== Messages sent to LLM ===")
    print(json.dumps(built, indent=2))

    print("\n=== LLM response (stub) ===")
    result = llm_call(built, config={"provider": "stub"}, system=SYSTEM_PROMPT)
    print(f"thinking : {result.thinking}")
    print(f"response : {result.response}")
    print(f"tool_call: {result.tool_call}")
