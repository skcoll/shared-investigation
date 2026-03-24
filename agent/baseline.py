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
You are an expert CTF analyst specialising in reverse engineering and cryptography.

Your goal is to analyse the given challenge and find the flag.

## Available tools
- strings(file)            : extract printable strings from a file
- hexdump(file, offset, n) : show n bytes of a file as hex starting at offset
- run_command(cmd)         : run a shell command and return stdout
- python_eval(code)        : execute a Python snippet and return the result

## How to respond
Think step by step. At each turn:
1. Describe what you observe and what you think it means.
2. State your current hypothesis about what the challenge is doing.
3. Choose one tool to call next and explain why.

If you believe you have found the flag, respond with:
FLAG: <your answer>

Be concise. One tool call per turn.
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
            {"role": "user", "content": f"{challenge_text}\n\nBegin your analysis."},
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
