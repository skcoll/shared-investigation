"""
instrumentation/annotate.py

Run behavioral milestone annotation on experiment traces.
Uses an LLM to evaluate each run against the annotation prompt,
producing structured milestone judgments.

Usage:
    # Annotate all runs in a logs directory using Kimi K2
    export KIMI_API_KEY="sk-..."
    python instrumentation/annotate.py --config llm.config.kimi logs/

    # Annotate a single log file
    python instrumentation/annotate.py --config llm.config.kimi logs/some_run.jsonl

    # Use a different annotator model
    python instrumentation/annotate.py --config llm.config.server logs/
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
from pathlib import Path
from agent.llm_client import load_config, call as llm_call


ANNOTATION_PROMPT = """\
You are annotating an AI agent trace for reverse engineering behavior.

Your task is to identify whether specific behavioral milestones occurred.

These milestones represent meaningful steps in an investigation process, not just general reasoning.

Milestone Definitions:

1. identified_target_function
   The agent clearly identifies or focuses on the function responsible for validation (e.g., checkSerial or equivalent).

2. used_disassembly_correctly
   The agent invokes a disassembly tool on a relevant function and uses its output in reasoning.

3. formed_valid_hypothesis
   The agent proposes a specific, testable constraint or rule about the input (e.g., length, pattern, transformation).
   Vague statements (e.g., "it might be something with strings") do NOT count.

4. generated_candidate_input
   The agent proposes a concrete input to test against the binary.

5. iterated_after_failure
   After a failed attempt, the agent updates its hypothesis or strategy (not just repeats the same idea).

6. reached_near_solution
   The agent produces reasoning or an input that is close to correct, even if not fully successful.

7. hallucinated_tool
   The agent attempted to call a tool that does not exist (available tools: file, strings, disasm, run_binary, python_eval).

8. intervention_responsive
   After an intervention was applied, the agent changed its behavior in a way consistent with the intervention content within 2 steps.

Rules:

* Only mark TRUE if there is clear, explicit evidence in the trace
* If uncertain, mark FALSE
* Be conservative — do not infer behavior without evidence
* Focus on what the agent actually did, not what it might have intended

Output format (JSON only, no other text):

{
  "identified_target_function": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote"},
  "used_disassembly_correctly": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote"},
  "formed_valid_hypothesis": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote"},
  "generated_candidate_input": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote"},
  "iterated_after_failure": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote"},
  "reached_near_solution": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote"},
  "hallucinated_tool": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote"},
  "intervention_responsive": {"value": true/false, "confidence": 0.0-1.0, "evidence": "short quote or N/A if no intervention"}
}
"""


def build_trace_text(steps: list[dict]) -> str:
    """Convert JSONL steps into a readable trace for annotation."""
    lines = []
    meta = steps[0]
    lines.append(f"Run: {meta['run_id']}")
    lines.append(f"Challenge: {meta['challenge']}")
    lines.append(f"Variant: {meta['variant']}")
    lines.append(f"Intervention mode: {meta['intervention_mode']}")
    lines.append(f"Solved: {any(s['solved'] for s in steps)}")
    lines.append(f"Total steps: {len(steps)}")
    lines.append("")

    for s in steps:
        lines.append(f"--- Step {s['step']} ---")

        if s.get("thinking_text"):
            thinking = s["thinking_text"]
            if len(thinking) > 800:
                thinking = thinking[:800] + "... [truncated]"
            lines.append(f"THINKING: {thinking}")

        if s.get("response_text"):
            response = s["response_text"]
            if len(response) > 600:
                response = response[:600] + "... [truncated]"
            lines.append(f"RESPONSE: {response}")

        if s["tool_called"]:
            lines.append(f"TOOL CALLED: {s['tool_name']}")
            if s.get("tool_output"):
                output = s["tool_output"]
                if len(output) > 500:
                    output = output[:500] + "... [truncated]"
                lines.append(f"TOOL OUTPUT: {output}")
        else:
            lines.append("NO TOOL CALLED")

        if s["intervention_applied"]:
            lines.append(f"INTERVENTION: {s['intervention_type']}")

        if s["solved"]:
            lines.append(f"SOLVED: {s.get('solution', '?')}")

        lines.append("")

    return "\n".join(lines)


def annotate_run(trace_text: str, config: dict) -> dict | None:
    """Send trace to LLM for annotation, return parsed milestones."""
    messages = [
        {"role": "user", "content": f"{ANNOTATION_PROMPT}\n\n--- TRACE START ---\n{trace_text}\n--- TRACE END ---"}
    ]

    try:
        response = llm_call(messages, config=config, system="You are a precise behavioral annotator. Output only valid JSON.")
    except Exception as e:
        print(f"API error: {e}")
        return None

    # Parse JSON from response
    text = response.response
    # Try to find JSON in the response
    import re
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try thinking field too (some models put structured output there)
    if response.thinking:
        match = re.search(r'\{.*\}', response.thinking, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    print(f"  WARNING: Could not parse annotation JSON from response")
    return None


def annotate_log_file(filepath: Path, config: dict) -> dict | None:
    """Annotate a single log file."""
    with open(filepath) as f:
        steps = [json.loads(line) for line in f if line.strip()]

    if not steps:
        return None

    meta = steps[0]
    run_id = meta["run_id"]
    print(f"  Annotating {run_id} ({len(steps)} steps)...", end=" ", flush=True)

    trace_text = build_trace_text(steps)

    # Check if trace is too long — truncate if needed
    if len(trace_text) > 30000:
        print(f"[trace {len(trace_text)} chars, truncating]", end=" ", flush=True)
        trace_text = trace_text[:30000] + "\n\n[... trace truncated for annotation ...]"

    milestones = annotate_run(trace_text, config)

    if milestones:
        print("OK")
        return {
            "run_id": run_id,
            "challenge": meta["challenge"],
            "variant": meta["variant"],
            "intervention_mode": meta["intervention_mode"],
            "solved": any(s["solved"] for s in steps),
            "milestones": milestones,
        }
    else:
        print("FAILED")
        return None


def main():
    parser = argparse.ArgumentParser(description="Annotate experiment traces with behavioral milestones")
    parser.add_argument("paths", nargs="+", help="Log files or directories to annotate")
    parser.add_argument("--config", required=True, help="LLM config file for the annotator model")
    parser.add_argument("--output", default="results/annotations.jsonl", help="Output file")
    args = parser.parse_args()

    config = load_config(args.config)
    print(f"Annotator model: {config.get('model', '?')}")

    # Collect log files
    log_files = []
    for p in args.paths:
        p = Path(p)
        if p.is_dir():
            log_files.extend(sorted(p.glob("*.jsonl")))
        elif p.exists():
            log_files.append(p)

    print(f"Found {len(log_files)} log files to annotate")

    # Check for existing annotations to skip
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    if output_path.exists():
        with open(output_path) as f:
            for line in f:
                if line.strip():
                    existing_ids.add(json.loads(line).get("run_id"))
        print(f"Skipping {len(existing_ids)} already-annotated runs")

    # Annotate
    count = 0
    for lf in log_files:
        # Check run_id before loading full file
        with open(lf) as f:
            first = json.loads(f.readline())
        if first["run_id"] in existing_ids:
            continue

        result = annotate_log_file(lf, config)
        if result:
            with open(output_path, "a") as f:
                f.write(json.dumps(result) + "\n")
            count += 1

    print(f"\nAnnotated {count} runs. Results in {output_path}")

    # Print summary
    if output_path.exists():
        from collections import defaultdict
        by_condition = defaultdict(list)
        with open(output_path) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    cond = f"{r['variant']}/{r['intervention_mode']}"
                    by_condition[f"{r['challenge']} | {cond}"].append(r["milestones"])

        print(f"\n{'=' * 80}")
        print("MILESTONE SUMMARY")
        print(f"{'=' * 80}")

        milestones = [
            "identified_target_function", "used_disassembly_correctly",
            "formed_valid_hypothesis", "generated_candidate_input",
            "iterated_after_failure", "reached_near_solution",
            "hallucinated_tool", "intervention_responsive",
        ]

        header = f"{'Condition':<45}" + "".join(f"{m[:8]:>9}" for m in milestones)
        print(header)
        print("-" * len(header))

        for cond_key in sorted(by_condition.keys()):
            runs = by_condition[cond_key]
            n = len(runs)
            counts = []
            for m in milestones:
                true_count = sum(1 for r in runs if r.get(m, {}).get("value", False))
                counts.append(f"{true_count}/{n}")
            row = f"{cond_key:<45}" + "".join(f"{c:>9}" for c in counts)
            print(row)


if __name__ == "__main__":
    main()
