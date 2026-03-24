# Shared Investigation Agent

A research prototype studying whether **explicit structured investigation state** enables effective coordination between human insight and AI exploration on cybersecurity CTF challenges.

## Research Question

Does making an LLM's investigation state explicit and shared — rather than implicit in conversation history — improve human-AI teaming on analytical tasks?

## Experimental Design

Two agent variants solve the same CTF challenges. Both run through the same loop, but differ in what the LLM sees:

| Condition | Agent | State Visible? | Interventions? |
|-----------|-------|----------------|----------------|
| A | Baseline | No | No |
| B | Structured | Yes | No |
| C | Structured | Yes | Light (add/reject hypothesis, mark important) |
| D (stretch) | Structured | Yes | Strong (suggest action, reprioritize) |

**Human proxies:** Real humans are replaced by multiple CTF writeups per challenge. Reasoning steps are extracted from writeups and aggregated into consensus traces, which become the source for scripted interventions.

## Architecture

```
                    ┌──────────────────────────┐
                    │      loop.py             │
                    │   (shared agent loop)    │
                    └────┬──────────┬──────────┘
                         │          │
              ┌──────────┘          └──────────┐
              ▼                                ▼
   ┌─────────────────────┐          ┌─────────────────────┐
   │   baseline.py       │          │   structured.py     │
   │ build_prompt():     │          │ build_prompt():     │
   │   history only      │          │   state + history   │
   │   state is HIDDEN   │          │   state is VISIBLE  │
   └─────────┬───────────┘          └─────────┬───────────┘
             │                                │
             └──────────┬─────────────────────┘
                        ▼
             ┌─────────────────────┐
             │   llm_client.py    │
             │                     │
             │ stub  │ vllm │ anthropic
             └─────────────────────┘
```

### Data Flow (one loop iteration)

1. `build_prompt_fn(state, messages)` constructs the prompt
2. LLM returns thinking + response + optional tool call
3. Loop parses state updates (observations, hypotheses, understanding)
4. Tool is executed, result recorded as `ActionRecord`
5. **Intervention point**: check for scripted intervention, apply if present
6. Append to message history, advance step

## Project Structure

```
.
├── state/
│   ├── schema.py              # Pydantic models (the core data structures)
│   └── test_schema.py         # Smoke test for schema
│
├── agent/
│   ├── loop.py                # Main agent loop (both variants use this)
│   ├── llm_client.py          # LLM provider abstraction (stub/vllm/anthropic)
│   ├── baseline.py            # Baseline prompt builder (control condition)
│   └── structured.py          # Structured prompt builder (experimental condition)
│
├── challenges/
│   ├── picoCTF2019_vaultdoor1/
│   │   ├── VaultDoor1.java    # Challenge source code
│   │   ├── vaultdoor1_problem.txt
│   │   └── writeup_*.pdf      # 5 student writeups
│   │
│   └── picoCTF2019_vaultdoor3/
│       ├── VaultDoor3.java    # Challenge source code
│       ├── vaultdoor3_problem.txt
│       ├── writeup_*.txt      # 5 raw writeup texts
│       └── writeup_*.json     # 5 extracted + normalized reasoning steps
│
└── writeupfetch.py            # Utility to fetch writeups from the web
```

## Core Data Model (`state/schema.py`)

Five Pydantic classes define the shared investigation state:

- **`Observation`** — a fact discovered via a tool (`id`, `content`, `source`, `step`, `important`)
- **`Hypothesis`** — a testable claim (`id`, `claim`, `status`, `confidence`, `origin`, `step_created`, `step_updated`)
- **`ActionRecord`** — a tool invocation and its result (`step`, `tool`, `arguments`, `result_summary`)
- **`Intervention`** — a human/scripted state mutation (`id`, `type`, `payload`, `step`, `source`)
- **`InvestigationState`** — the top-level container holding all of the above plus `next_steps`, `current_understanding`, `flag_candidate`, and `solved`

Key design choices:
- `Hypothesis.origin` is `"agent"` or `"intervention"` — this is how we measure whether the agent adopted externally-provided hypotheses
- `Observation.important` is only set via the `mark_observation_as_important` intervention
- `next_steps` is a plain `list[str]` (not a separate class) to keep things minimal

## Agent Variants

### Baseline (`agent/baseline.py`)

The **control condition**. The LLM receives:
- A system prompt describing the task and available tools
- The conversation history

`InvestigationState` exists in the loop and is updated from responses, but is **never shown to the model**. The model reasons purely from its own conversation history.

### Structured (`agent/structured.py`)

The **experimental condition**. The LLM receives everything the baseline gets, plus:
- The current `InvestigationState` rendered as readable text at the top of every message
- An `update_investigation_state` tool schema it must call each turn to update state
- Instructions to treat intervention-origin hypotheses as "a colleague's input"

`render_state()` converts the Pydantic object into human-readable markdown, including `[IMPORTANT]` flags on observations and `[from intervention]` tags on hypotheses.

## LLM Client (`agent/llm_client.py`)

A thin wrapper returning a consistent `LLMResponse(thinking, response, tool_call)` across four providers:

| Provider | Use Case | Thinking Extraction |
|----------|----------|---------------------|
| `stub` | Testing without any API | Hardcoded response |
| `vllm` | Local vLLM server (DeepSeek R1) | Parsed from `<think>...</think>` tags if present |
| `ollama` | Local Ollama server (Llama, etc.) | Parsed from `<think>...</think>` tags if present |
| `anthropic` | Claude API | Separate `thinking` content block |

`vllm` and `ollama` share the same OpenAI-compatible code path. Any model that emits `<think>` tags gets its reasoning parsed out; models that don't simply return an empty `thinking` string.

Example configs:

```python
# Ollama with llama3.1:8b
{"provider": "ollama", "model": "llama3.1:8b", "base_url": "http://localhost:11434/v1"}

# vLLM with DeepSeek R1
{"provider": "vllm", "model": "deepseek-r1", "base_url": "http://localhost:8000/v1"}
```

## Intervention Types

Interventions are typed mutations to `InvestigationState`, not free-text hints:

| Type | Category | Effect |
|------|----------|--------|
| `add_hypothesis` | Light | Adds a new hypothesis with `origin="intervention"` |
| `reject_hypothesis` | Light | Sets an existing hypothesis status to `"refuted"` |
| `mark_observation_as_important` | Light | Flags an observation for the agent's attention |
| `suggest_action` | Strong | Proposes a specific tool call |
| `reprioritize_next_steps` | Strong | Reorders the agent's next-steps list |

Currently `add_hypothesis` is implemented in `loop.py`; the rest are stubbed and will live in `state/intervention.py`.

## Writeup Processing Pipeline

Each challenge has multiple writeups that serve as human reasoning proxies:

1. **Fetch** — `writeupfetch.py` pulls writeup text from URLs
2. **Extract** — reasoning steps are extracted into JSON with schema: `{"source", "steps": [{"type", "content", "evidence"}]}`
3. **Normalize** — duplicates merged, vague steps removed, hypotheses made testable, steps made atomic

Step types: `observation`, `hypothesis`, `action`, `result`.

For `picoCTF2019_vaultdoor3`, 5 writeups have been extracted and normalized (3-9 steps each).

## Running

```bash
# Setup
python3 -m venv .venv
.venv/bin/pip install pydantic openai

# Test the schema
.venv/bin/python state/test_schema.py

# Run the loop skeleton (uses stubs, no API needed)
.venv/bin/python agent/loop.py

# Run with a local Ollama model (requires: ollama serve && ollama pull llama3.1:8b)
# Update the config dict in your run script to:
#   {"provider": "ollama", "model": "llama3.1:8b", "base_url": "http://localhost:11434/v1"}

# Test individual agents
.venv/bin/python agent/baseline.py
.venv/bin/python agent/structured.py

# Test the LLM client
.venv/bin/python agent/llm_client.py
```

## Not Yet Implemented

- `state/intervention.py` — full `apply_intervention()` for all 5 intervention types
- `agent/tools.py` — the 4 tools: `strings`, `hexdump`, `run_command`, `python_eval`
- `instrumentation/logger.py` — JSONL step logger
- `instrumentation/metrics.py` — solve rate, steps to solve, intervention uptake
- `experiments/run.py` — CLI entry point to run conditions across challenges
- Wiring `loop.py` to use real LLM calls instead of stubs
- Challenge metadata and scripted intervention files
