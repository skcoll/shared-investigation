# Shared Investigation Agent

A research prototype for studying whether **explicit structured investigation state** improves human–AI coordination on reverse engineering tasks.

## Research Question

Does making an LLM agent's investigation state explicit and shared—rather than implicit in conversation history—improve reasoning quality, tool usage, and responsiveness to human guidance?

## Motivation

Reverse engineering is an inherently iterative, hypothesis-driven process: an analyst inspects a binary, forms hypotheses about its behavior, tests them through execution, and refines understanding over multiple cycles. This makes it a strong testbed for studying structured human–AI collaboration.

We compare two agent configurations on the same tasks to isolate the effect of state visibility:

- **Baseline**: the LLM sees only a system prompt and conversation history. Investigation state is maintained internally but never shown to the model.
- **Structured**: the LLM additionally receives a rendered investigation state (observations, hypotheses, actions, current focus) at every turn and is required to update it.

Both variants share the same loop, tools, and interventions. The only difference is prompt construction.

## Experimental Design

We use a factorial design crossing state visibility with intervention strength:

| Condition | State Visible | Interventions |
|-----------|--------------|---------------|
| A | No | None |
| B | No | Light |
| C | Yes | None |
| D | Yes | Light |
| E | Yes | Strong |

**Intervention types.** Light interventions provide directional guidance: `add_hypothesis`, `reject_hypothesis`, `mark_observation_important`. Strong interventions prescribe actions: `suggest_action`, `reprioritize_next_steps`.

**Stall-based delivery.** Interventions fire after N consecutive steps with no new tool called (default N=3), delivering the next hint from a tiered queue. This is deterministic given the same run trace.

**Human proxies.** Interventions are derived from multiple independently authored writeups for each challenge via a reproducible LLM-assisted pipeline (see `methodology/intervention_derivation.md`).

## System Architecture

```
loop.py ─── build_prompt() ─── LLM ─── parse response
               │                           │
        baseline.py or              TOOL: name(args)
        structured.py                      │
                                     tools.py
                                   file | strings | disasm
                                   run_binary | python_eval
                                           │
                                    tool output fed back ──→ next step
                                           │
                                    instrumentation/logger.py
                                    (JSONL per-step logging)
```

**Agent loop (per step):**
1. Construct prompt (with or without state, depending on condition)
2. Call LLM; receive thinking trace and response
3. Parse tool request from response (`TOOL: name(args)`)
4. Execute tool and return output to the model
5. Parse structured state update (structured variant only)
6. Check for solution (explicit `SOLUTION:` or binary accepted input)
7. Compute derived metrics (action gap, repeated tool, novel tool)
8. Apply scripted intervention if stall detected
9. Log step record to JSONL

## Tools

| Tool | Description | Execution |
|------|-------------|-----------|
| `file()` | File type and metadata | Local |
| `strings()` | Printable strings from binary | Local |
| `disasm()` | Full binary disassembly (Intel syntax) | Local (objdump) |
| `disasm(FUNCTION)` | Disassemble a specific function | Local (objdump) |
| `run_binary(INPUT)` | Execute binary with given argument | Docker (linux/amd64) |
| `python_eval(CODE)` | Run a Python snippet | Local |

`run_binary` uses Docker to execute x86-64 Linux ELF binaries on macOS ARM via Rosetta. Input validation guards return helpful errors for empty arguments.

## Investigation State

The shared state is a Pydantic model (`InvestigationState`) containing:

- **Observations** — facts discovered via tools, with source attribution
- **Hypotheses** — testable claims with status (`active`/`supported`/`refuted`), confidence, and origin (`agent` or `intervention`)
- **Actions** — tool calls and their results
- **Current focus** — what the agent is currently investigating
- **Current understanding** — free-text summary maintained by the agent

The `origin` field on hypotheses is the primary mechanism for measuring intervention uptake.

## Models

We use **DeepSeek R1** at two scales plus a frontier reference:

| Model | Params | Role | Provider |
|-------|--------|------|----------|
| **DeepSeek R1 14B** | 14B | Small-scale — tests whether structured state changes behavior when the model cannot independently solve | Ollama (school GPU server) |
| **DeepSeek R1 70B** | 70B | Large-scale — tests whether the structured state advantage persists with stronger reasoning | Ollama (school GPU server) |
| **Kimi K2 Thinking** | ~1T MoE | Frontier ceiling — tests whether the effect persists when model capability is no longer the bottleneck | Moonshot API |

**Why DeepSeek R1.** (1) Native thinking traces — the `<think>` block is trained into the model via reinforcement learning, providing explicit chain-of-thought data without prompt engineering. (2) Same architecture at multiple scales — 14B and 70B differ only in parameter count, isolating scale as a variable. (3) Open-weight and reproducible — freely available via Ollama, enabling full reproducibility without API costs. (4) Reasoning-optimized — trained with RL specifically for reasoning tasks, making it well-suited to investigative RE.

**LLM client** (`llm_client.py`) supports four backends: Ollama (native API, preserves thinking traces), vLLM (OpenAI-compatible), Moonshot/Kimi (OpenAI-compatible with `reasoning_content`), Anthropic (extended thinking), and a stub for testing. Model configuration is specified in JSON files. API keys support `"env:VAR_NAME"` syntax.

## Logging and Metrics

Each step produces a structured JSONL record (18 fields) capturing:
- Condition metadata (variant, intervention mode, run ID)
- Tool usage (called, name, success, repeated, novel)
- Intervention application (applied, type)
- Response and thinking lengths
- Action gap detection (model describes an action but does not execute it)
- Solve status

**Derived metrics** (`instrumentation/metrics.py`):
- **solve_rate** — fraction of runs that found a valid solution
- **steps_to_solve** — steps used in solved runs
- **tool_diversity** — unique tools per run
- **repeated_tool_rate** — fraction of steps repeating the previous tool
- **intervention_uptake** — intervention at step t AND tool called at t+1
- **action_gap_rate** — model describes action without executing it

## Results

### Completed: DeepSeek R1 14B (yurisimplekeygen, 3 runs/condition, 15-step budget)

| Condition | Solve Rate | Avg Tools | Unique Tools | Action Gap |
|-----------|-----------|-----------|--------------|------------|
| A: baseline/none | 0/3 | 5.7 | 1.7 | 0.600 |
| B: baseline/light | 0/3 | 3.3 | 1.0 | 0.778 |
| C: structured/none | 0/3 | 5.7 | 2.7 | 0.356 |
| D: structured/light | 0/3 | 10.3 | 4.3 | 0.156 |
| E: structured/strong | 0/3 | 7.3 | 3.7 | 0.222 |

No condition solved, but structured state reduced action gap from ~69% to ~24% and tripled tool diversity.

### Completed: Kimi K2 Frontier Reference (yurisimplekeygen, 3 runs/condition, 20-step budget)

| Condition | Solve Rate | Avg Steps | Avg Tools | Unique Tools | Action Gap |
|-----------|-----------|-----------|-----------|--------------|------------|
| A: baseline/none | 3/3 | 10.3 | 9.3 | 5.0 | 0.107 |
| B: baseline/light | 3/3 | 8.3 | 7.3 | 4.3 | 0.122 |
| C: structured/none | 3/3 | 10.3 | 9.3 | 5.3 | 0.048 |
| D: structured/light | 3/3 | 12.7 | 12.0 | 5.3 | 0.022 |
| E: structured/strong | 2/3 | 11.0 | 12.0 | 5.7 | 0.042 |

All conditions solve, but structured state still reduces action gap by ~65%.

### Pending: DeepSeek R1 70B (yurisimplekeygen)

The critical middle data point. Same architecture as 14B at 5× scale — will show whether structured state's behavioral advantages translate to solve rate differences with a more capable open-weight model.

### Cross-Model Summary (to date)

| | DeepSeek R1 14B | DeepSeek R1 70B | Kimi K2 |
|---|---|---|---|
| Solve rate (baseline) | 0/6 | *pending* | 6/6 |
| Solve rate (structured) | 0/9 | *pending* | 8/9 |
| Action gap (baseline) | 0.689 | *pending* | 0.114 |
| Action gap (structured) | 0.245 | *pending* | 0.037 |
| Action gap reduction | 64% | *pending* | 68% |

See `results/` for full analysis files.

## Repository Structure

```
state/schema.py                  Investigation state data model
agent/loop.py                    Main agent loop with experiment controls
agent/baseline.py                Baseline prompt builder (control)
agent/structured.py              Structured prompt builder (experimental)
agent/llm_client.py              LLM provider abstraction
agent/tools.py                   Tool execution (local + Docker)
instrumentation/logger.py        JSONL step logging (18 fields per step)
instrumentation/metrics.py       Compute metrics from JSONL logs
methodology/                     Intervention derivation methodology + prompts
challenges/<id>/                 Challenge data (binary, writeups, interventions)
results/                         Experiment analysis and metrics
run_experiment.sh                DeepSeek R1 14B experiment runner
run_full_experiment.sh           Kimi K2 full factorial experiment runner
llm.config                       Default LLM config (Ollama local)
llm.config.server                School server config (Ollama remote)
llm.config.qwen3                 Qwen3 8B config
```

## Usage

```bash
# Setup
python3 -m venv .venv && .venv/bin/pip install pydantic openai
docker pull --platform linux/amd64 ubuntu:22.04

# Run a single condition
.venv/bin/python agent/loop.py \
  --challenge yurisimplekeygen \
  --structured \
  --interventions light \
  --steps 20

# Conditions:
#   A: (default)                    B: --interventions light
#   C: --structured                 D: --structured --interventions light
#   E: --structured --interventions strong

# Use a specific model config
.venv/bin/python agent/loop.py --config llm.config.qwen3 --challenge yurisimplekeygen

# For Kimi K2 (requires API key)
export KIMI_API_KEY="sk-..."
.venv/bin/python agent/loop.py --config llm.config.kimi --challenge yurisimplekeygen

# Run full factorial experiment
bash run_full_experiment.sh

# Compute metrics from logs
.venv/bin/python instrumentation/metrics.py logs/
```

## Adding a New Challenge

```bash
# Scaffold
.venv/bin/python challenges/init_challenge.py my_challenge

# Add binary to artifacts/, writeup JSONs to hints/, create interventions.json
# Regenerate metadata
.venv/bin/python challenges/init_challenge.py my_challenge

# Run
.venv/bin/python agent/loop.py --challenge my_challenge --steps 20
```

## Work Remaining

- **DeepSeek R1 70B experiment**: full factorial on yurisimplekeygen — the critical scaling data point (in progress)
- **Harder challenges**: yurisimplekeygen (difficulty 1.5) is too easy for frontier models. Need 2-3 crackmes at difficulty 3-4 where baseline fails but structured may succeed.
- **More runs**: increase to 10 runs/condition for statistical power
- **Investigation milestones**: track intermediate progress (discovered function name, identified length, identified pattern) beyond binary solve/fail

## License

Research prototype. Not intended for production use.
