"""
instrumentation/metrics.py

Compute experiment metrics from JSONL log files.
Each log file contains one JSON object per step.

Usage:
    python instrumentation/metrics.py logs/
    python instrumentation/metrics.py logs/yurisimplekeygen_*.jsonl
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def load_run(filepath: Path) -> list[dict]:
    """Load all step records from a JSONL file."""
    records = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def compute_run_metrics(steps: list[dict]) -> dict:
    """Compute metrics for a single run."""
    if not steps:
        return {}

    meta = steps[0]
    solved = any(s["solved"] for s in steps)
    solve_step = None
    if solved:
        for s in steps:
            if s["solved"]:
                solve_step = s["step"]
                break

    VALID_TOOLS = {"file", "strings", "disasm", "run_binary", "python_eval"}

    tool_calls = [s for s in steps if s["tool_called"]]
    all_tool_names = set(s["tool_name"] for s in tool_calls)
    valid_tools_used = all_tool_names & VALID_TOOLS
    hallucinated_tools = all_tool_names - VALID_TOOLS
    total_steps = len(steps)

    # Tool diversity
    tool_counts = defaultdict(int)
    for s in tool_calls:
        tool_counts[s["tool_name"]] += 1

    # Repeated tool rate
    repeated = sum(1 for s in steps if s["repeated_tool"])
    repeated_rate = repeated / total_steps if total_steps > 0 else 0

    # Action gap rate
    action_gaps = sum(1 for s in steps if s["action_gap"])
    action_gap_rate = action_gaps / total_steps if total_steps > 0 else 0

    # Intervention uptake: intervention at step t AND tool_called at t+1
    intervention_steps = [s["step"] for s in steps if s["intervention_applied"]]
    step_lookup = {s["step"]: s for s in steps}
    uptake_count = 0
    for iv_step in intervention_steps:
        next_step = step_lookup.get(iv_step + 1)
        if next_step and next_step["tool_called"]:
            uptake_count += 1
    uptake_rate = uptake_count / len(intervention_steps) if intervention_steps else None

    # Average response and thinking lengths
    avg_response_len = sum(s["response_length"] for s in steps) / total_steps
    avg_thinking_len = sum(s["thinking_length"] for s in steps) / total_steps

    return {
        "run_id": meta["run_id"],
        "challenge": meta["challenge"],
        "variant": meta["variant"],
        "intervention_mode": meta["intervention_mode"],
        "condition": f"{meta['variant']}/{meta['intervention_mode']}",
        "total_steps": total_steps,
        "solved": solved,
        "solve_step": solve_step,
        "tool_calls": len(tool_calls),
        "unique_tools": len(valid_tools_used),
        "hallucinated_tools": len(hallucinated_tools),
        "hallucinated_tool_names": sorted(hallucinated_tools),
        "tool_distribution": dict(tool_counts),
        "repeated_tool_rate": round(repeated_rate, 3),
        "action_gap_rate": round(action_gap_rate, 3),
        "interventions_fired": len(intervention_steps),
        "intervention_uptake": uptake_count,
        "intervention_uptake_rate": round(uptake_rate, 3) if uptake_rate is not None else None,
        "avg_response_length": round(avg_response_len, 0),
        "avg_thinking_length": round(avg_thinking_len, 0),
    }


def aggregate_by_condition(run_metrics: list[dict]) -> dict:
    """Aggregate run-level metrics by condition."""
    by_condition = defaultdict(list)
    for rm in run_metrics:
        by_condition[rm["condition"]].append(rm)

    summary = {}
    for condition, runs in sorted(by_condition.items()):
        n = len(runs)
        solved_runs = [r for r in runs if r["solved"]]
        solve_steps = [r["solve_step"] for r in solved_runs if r["solve_step"]]

        summary[condition] = {
            "n_runs": n,
            "solve_rate": f"{len(solved_runs)}/{n}",
            "solve_rate_pct": round(100 * len(solved_runs) / n, 1) if n > 0 else 0,
            "avg_steps_to_solve": round(sum(solve_steps) / len(solve_steps), 1) if solve_steps else None,
            "avg_tool_calls": round(sum(r["tool_calls"] for r in runs) / n, 1),
            "avg_unique_tools": round(sum(r["unique_tools"] for r in runs) / n, 1),
            "avg_action_gap_rate": round(sum(r["action_gap_rate"] for r in runs) / n, 3),
            "avg_repeated_tool_rate": round(sum(r["repeated_tool_rate"] for r in runs) / n, 3),
            "avg_response_length": round(sum(r["avg_response_length"] for r in runs) / n, 0),
            "avg_thinking_length": round(sum(r["avg_thinking_length"] for r in runs) / n, 0),
            "intervention_uptake_rates": [
                r["intervention_uptake_rate"] for r in runs
                if r["intervention_uptake_rate"] is not None
            ],
        }

    return summary


def print_report(run_metrics: list[dict], summary: dict) -> str:
    """Format a human-readable report."""
    lines = []
    lines.append("=" * 72)
    lines.append("EXPERIMENT METRICS REPORT")
    lines.append("=" * 72)

    # Per-condition summary
    lines.append("\nCONDITION SUMMARY")
    lines.append("-" * 72)
    header = f"{'Condition':<25} {'Solve':>6} {'Steps':>6} {'Tools':>6} {'Uniq':>5} {'ActGap':>7} {'Repeat':>7} {'RspLen':>7}"
    lines.append(header)
    lines.append("-" * 72)

    for condition, s in summary.items():
        solve_str = s["solve_rate"]
        steps_str = str(s["avg_steps_to_solve"]) if s["avg_steps_to_solve"] else "—"
        lines.append(
            f"{condition:<25} {solve_str:>6} {steps_str:>6} "
            f"{s['avg_tool_calls']:>6.1f} {s['avg_unique_tools']:>5.1f} "
            f"{s['avg_action_gap_rate']:>7.3f} {s['avg_repeated_tool_rate']:>7.3f} "
            f"{s['avg_response_length']:>7.0f}"
        )

    # Per-run details
    lines.append("\n\nPER-RUN DETAILS")
    lines.append("-" * 72)
    for rm in run_metrics:
        solved_str = f"SOLVED step {rm['solve_step']}" if rm["solved"] else "NOT SOLVED"
        lines.append(
            f"  {rm['run_id']}  {rm['condition']:<25} {solved_str:<20} "
            f"tools={rm['tool_calls']} uniq={rm['unique_tools']} "
            f"gaps={rm['action_gap_rate']:.2f} "
            f"iv_uptake={rm['intervention_uptake_rate'] if rm['intervention_uptake_rate'] is not None else '—'}"
        )
        if rm["tool_distribution"]:
            lines.append(f"    tool dist: {rm['tool_distribution']}")

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


def main():
    """Load all JSONL files from args, compute and print metrics."""
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <logs_dir_or_files...>")
        sys.exit(1)

    # Collect log files
    log_files = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            log_files.extend(sorted(p.glob("*.jsonl")))
        elif p.exists():
            log_files.append(p)

    if not log_files:
        print("No JSONL files found.")
        sys.exit(1)

    print(f"Loading {len(log_files)} log files...")

    # Compute per-run metrics
    run_metrics = []
    for lf in log_files:
        steps = load_run(lf)
        if steps:
            rm = compute_run_metrics(steps)
            run_metrics.append(rm)

    # Aggregate by condition
    summary = aggregate_by_condition(run_metrics)

    # Print report
    report = print_report(run_metrics, summary)
    print(report)

    # Also save as JSON for programmatic use
    output_path = Path("results/metrics.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "runs": run_metrics,
        "summary": summary,
    }, indent=2))
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
