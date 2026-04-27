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
- **unique_tools** — distinct tools from the valid set {file, strings, disasm, run_binary, python_eval} called per run; hallucinated tool names (objdump, checksec, etc.) are excluded
- **repeated_tool_rate** — fraction of steps repeating the previous tool
- **intervention_uptake** — fraction of interventions at step t followed by a tool call at step t+1
- **action_gap_rate** — fraction of steps where the agent describes an action ("I'll run...", "I should try...") but does not emit a tool call

**Example calculation** for a 10-step run:

| Step | Response | Tool | Notes |
|------|----------|------|-------|
| 1 | "Let me examine the binary" | `file()` | |
| 2 | "I'll try running strings next" | — | **action gap** |
| 3 | "I'll run strings on the binary" | `strings()` | |
| 4 | "I should disassemble main" | — | **action gap** |
| 5 | "Let me disassemble checkSerial" | `disasm(checkSerial)` | intervention fired here |
| 6 | "I'll test a candidate input" | `run_binary(ABCDE...)` | **intervention uptake**: tool at t+1 |
| 7 | "That failed, trying next pattern" | `run_binary(BCDE...)` | |
| 8 | "Let me verify with python" | `python_eval(...)` | |
| 9 | "I'll use objdump for more detail" | — | **action gap** + hallucinated tool name |
| 10 | SOLUTION: BCDEFGHIJKLMNOPQ | — | solved |

- `action_gap_rate` = 3/10 = **0.30** (steps 2, 4, 9)
- `unique_tools` = **5** (file, strings, disasm, run_binary, python_eval — objdump excluded)
- `intervention_uptake` = 1/1 = **1.0** (one intervention at step 5, tool call followed at step 6)
- `solve_rate` = solved at step 10

## Results

**All 90 runs complete.** Full factorial (5 conditions × 3 models × 2 challenges × 3 runs). Annotated with LLM-as-judge (Kimi K2) for 8 behavioral milestones.

### Challenge: yurisimplekeygen (easy crackme, 16-char sequential password)

Solve rates and action gap per model per condition (3 runs each, 20-step budget):

| Condition | Kimi K2 | R1 70B | R1 14B | Total | Solve % | Action Gap |
|-----------|---------|--------|--------|-------|---------|------------|
| A: baseline/none | 3/3 | 0/3 | 0/3 | 3/9 | 33% | 0.444 |
| B: baseline/light | 3/3 | 2/3 | 0/3 | 5/9 | 56% | 0.384 |
| C: structured/none | 3/3 | 1/3 | 0/3 | 4/9 | 44% | 0.251 |
| D: structured/light | 3/3 | 3/3 | 0/3 | 6/9 | **67%** | 0.286 |
| E: structured/strong | 3/3 | 2/3 | 1/3 | 6/9 | **67%** | 0.238 |

Key findings:
- **70B benefits most from structured+light**: 0/3 → 3/3 (conditions A vs D), the only setting to reach 100% at this scale
- **14B never solves baseline** but structured+strong yields the first solve (1/3); structured state halves action gap even when the model cannot independently succeed
- **Kimi K2 solves all conditions**; structured state does not change solve rate but eliminates action gap entirely (0.16 → 0.00)
- **Action gap reduction**: ~37% lower in structured conditions across all models (0.41 baseline avg → 0.26 structured avg)

### Challenge: login_cipher (hard crackme, runtime-decoded strings + cipher check)

**0/45 solves across all models and conditions.** Requires understanding a runtime string decoder and a multi-step cipher transformation — beyond the current step budget and tool set. Used as a hard-challenge behavioral baseline: milestone depth, tool usage patterns, and intervention response are measured but solve rate is not expected.

### Behavioral Milestones (yurisimplekeygen, LLM-as-judge annotations, n=9 per row)

| Milestone | Baseline (A+B) | Structured (C+D+E) |
|-----------|:--------------:|:-----------------:|
| Identified target function | 13/18 (72%) | **27/27 (100%)** |
| Used disassembly correctly | 11/18 (61%) | **25/27 (93%)** |
| Formed valid hypothesis | 13/18 (72%) | **23/27 (85%)** |
| Generated candidate input | 8/18 (44%) | 18/27 (67%) |
| Reached near solution | 5/18 (28%) | **16/27 (59%)** |
| Hallucinated tool | 2/18 (11%) | **12/27 (44%)** |

Structured agents consistently identify the target function and apply disassembly at higher rates. The hallucination effect is a notable side finding: the state schema primes the model to emit tool-like syntax, causing it to invent names (`objdump`, `checksec`, `radare2`, `xrefs`) not in the available set. Valid unique tool counts are filtered to the 5 real tools only.

### Cross-Model Summary (yurisimplekeygen, all conditions)

| | DeepSeek R1 14B | DeepSeek R1 70B | Kimi K2 |
|---|---|---|---|
| Solve rate — baseline (A+B) | 0/6 | 2/6 | 6/6 |
| Solve rate — structured (C+D+E) | 1/9 | 6/9 | 9/9 |
| Action gap — baseline | 0.763 | 0.510 | 0.135 |
| Action gap — structured | 0.316 | 0.296 | 0.004 |
| Action gap reduction | 59% | 42% | 97% |

See `results/metrics.json` for per-run data and `results/annotations.jsonl` for milestone judgments.

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

- **Statistical power**: 3 runs/condition is sufficient for behavioral trends but not significance testing. Increasing to 10 runs/condition would enable proper comparisons.
- **Harder challenges**: yurisimplekeygen (difficulty ~1.5) is too easy for frontier models; login_cipher is too hard for all. Need 2-3 crackmes at difficulty 3-4 where baseline fails but structured may succeed.
- **Human subject component**: current work studies agent behavior under scripted human-proxy interventions. A proper coordination study would require real analysts interacting with the shared state in real time.
- **Paper writeup**: tables and figures from final results need to be incorporated into `paper/updated_main.tex`.

## License

Research prototype. Not intended for production use.
