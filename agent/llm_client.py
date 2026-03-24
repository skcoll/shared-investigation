"""
agent/llm_client.py

Thin wrapper around LLM providers. Returns a consistent LLMResponse regardless
of provider. Supports:
  - "stub"      : fake responses for testing without any API
  - "vllm"      : local vLLM server (OpenAI-compatible), e.g. DeepSeek R1
  - "ollama"    : local Ollama server (OpenAI-compatible), e.g. llama3.1:8b
  - "anthropic" : Anthropic API (Claude)

Models that embed reasoning inside <think>...</think> tags (e.g. DeepSeek R1)
have those parsed out into the thinking field. Models without think tags
simply return an empty thinking string.

Anthropic returns extended thinking as a separate content block.
"""

import json
import os
import re
from dataclasses import dataclass, field

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "llm.config")


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    thinking: str        # chain-of-thought / reasoning trace
    response: str        # final response text
    tool_call: dict | None = None  # {"name": str, "arguments": dict} or None


# ---------------------------------------------------------------------------
# Stub provider — no dependencies, useful for testing loop.py
# ---------------------------------------------------------------------------

def _stub_call(messages: list[dict], **kwargs) -> LLMResponse:
    last = messages[-1]["content"] if messages else ""
    return LLMResponse(
        thinking="[stub] I will examine the binary with strings first.",
        response="I'll run strings on the binary to look for hardcoded values.",
        tool_call={"name": "strings", "arguments": {"file": "target"}},
    )


# ---------------------------------------------------------------------------
# OpenAI-compatible provider (shared by vLLM and Ollama)
# Parses <think>...</think> if present; otherwise thinking is empty.
# ---------------------------------------------------------------------------

def _parse_think_tags(content: str) -> tuple[str, str]:
    """Split <think>...</think> from the rest of the response."""
    match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
    if match:
        thinking = match.group(1).strip()
        response = content[match.end():].strip()
    else:
        thinking = ""
        response = content.strip()
    return thinking, response


def _openai_compat_call(
    messages: list[dict],
    model: str,
    base_url: str,
    api_key: str = "none",
    tools: list[dict] | None = None,
    **kwargs,
) -> LLMResponse:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package required for vllm/ollama provider: pip install openai")

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=600.0)

    call_kwargs = dict(model=model, messages=messages, **kwargs)
    if tools:
        call_kwargs["tools"] = tools

    completion = client.chat.completions.create(**call_kwargs)
    message = completion.choices[0].message

    # Parse thinking out of content
    content = message.content or ""
    thinking, response = _parse_think_tags(content)

    # Extract tool call if present
    tool_call = None
    if message.tool_calls:
        tc = message.tool_calls[0]
        tool_call = {
            "name": tc.function.name,
            "arguments": json.loads(tc.function.arguments),
        }

    return LLMResponse(thinking=thinking, response=response, tool_call=tool_call)


# ---------------------------------------------------------------------------
# Anthropic provider
# Extended thinking is returned as a separate content block.
# ---------------------------------------------------------------------------

def _anthropic_call(
    messages: list[dict],
    model: str,
    api_key: str,
    system: str = "",
    tools: list[dict] | None = None,
    thinking_budget: int = 8000,
    **kwargs,
) -> LLMResponse:
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package required: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)

    call_kwargs = dict(
        model=model,
        messages=messages,
        betas=["interleaved-thinking-2025-05-14"],
        thinking={"type": "enabled", "budget_tokens": thinking_budget},
        max_tokens=thinking_budget + 4096,
        **kwargs,
    )
    if system:
        call_kwargs["system"] = system
    if tools:
        call_kwargs["tools"] = tools

    response_msg = client.beta.messages.create(**call_kwargs)

    thinking = ""
    response = ""
    tool_call = None

    for block in response_msg.content:
        if block.type == "thinking":
            thinking = block.thinking
        elif block.type == "text":
            response = block.text
        elif block.type == "tool_use":
            tool_call = {"name": block.name, "arguments": block.input}

    return LLMResponse(thinking=thinking, response=response, tool_call=tool_call)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Load LLM config from a JSON file (default: llm.config at project root).

    Values starting with "env:" are resolved from environment variables.
    Example: "api_key": "env:ANTHROPIC_API_KEY"
    """
    with open(path) as f:
        config = json.load(f)

    # Resolve env: references
    for key, value in config.items():
        if isinstance(value, str) and value.startswith("env:"):
            env_var = value[4:]
            resolved = os.environ.get(env_var)
            if not resolved:
                raise ValueError(f"Config references {value!r} but ${env_var} is not set")
            config[key] = resolved

    return config


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def call(
    messages: list[dict],
    config: dict,
    system: str = "",
    tools: list[dict] | None = None,
) -> LLMResponse:
    """
    Call the LLM and return a normalised LLMResponse.

    config keys:
      provider  : "stub" | "vllm" | "ollama" | "anthropic"
      model     : model name/id
      base_url  : vLLM/Ollama — e.g. "http://localhost:11434/v1"
      api_key   : vLLM (can be "none"), Ollama (defaults to "ollama"), or Anthropic key
    """
    provider = config.get("provider", "stub")

    if provider == "stub":
        return _stub_call(messages)

    if provider in ("vllm", "ollama"):
        default_key = "ollama" if provider == "ollama" else "none"
        return _openai_compat_call(
            messages=messages,
            model=config["model"],
            base_url=config["base_url"],
            api_key=config.get("api_key", default_key),
            tools=tools,
        )

    if provider == "anthropic":
        return _anthropic_call(
            messages=messages,
            model=config["model"],
            api_key=config["api_key"],
            system=system,
            tools=tools,
        )

    raise ValueError(f"Unknown provider: {provider!r}. Choose stub | vllm | ollama | anthropic")


# ---------------------------------------------------------------------------
# Manual test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    messages = [{"role": "user", "content": "Analyse this binary for me."}]
    result = call(messages, config={"provider": "stub"})
    print(f"thinking : {result.thinking}")
    print(f"response : {result.response}")
    print(f"tool_call: {result.tool_call}")
