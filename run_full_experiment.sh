#!/bin/bash
set -e

export KIMI_API_KEY="sk-HnoCM3euRWEioWZZfu1IJZqZ7TwXE7uNe0TggIi71ovP2Xyj"

CHALLENGE="yurisimplekeygen"
STEPS=20
CONFIG="llm.config.kimi"
RUNS=3

echo "========================================"
echo "FULL FACTORIAL EXPERIMENT"
echo "Model: Kimi K2 Thinking (Moonshot API)"
echo "Challenge: $CHALLENGE"
echo "Conditions: 5 (A-E) x $RUNS runs = $((5 * RUNS)) total"
echo "Budget: $STEPS steps per run"
echo "========================================"
echo ""

# Condition A: baseline, no interventions
for i in $(seq 1 $RUNS); do
  echo ">>> Condition A (baseline/none) - Run $i/3"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --interventions none --steps $STEPS --run-id "A_${i}" 2>&1 | tail -5
  echo ""
done

# Condition B: baseline, light interventions
for i in $(seq 1 $RUNS); do
  echo ">>> Condition B (baseline/light) - Run $i/3"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --interventions light --steps $STEPS --run-id "B_${i}" 2>&1 | tail -5
  echo ""
done

# Condition C: structured, no interventions
for i in $(seq 1 $RUNS); do
  echo ">>> Condition C (structured/none) - Run $i/3"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --structured --interventions none --steps $STEPS --run-id "C_${i}" 2>&1 | tail -5
  echo ""
done

# Condition D: structured, light interventions
for i in $(seq 1 $RUNS); do
  echo ">>> Condition D (structured/light) - Run $i/3"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --structured --interventions light --steps $STEPS --run-id "D_${i}" 2>&1 | tail -5
  echo ""
done

# Condition E: structured, strong interventions
for i in $(seq 1 $RUNS); do
  echo ">>> Condition E (structured/strong) - Run $i/3"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --structured --interventions strong --steps $STEPS --run-id "E_${i}" 2>&1 | tail -5
  echo ""
done

echo "========================================"
echo "ALL RUNS COMPLETE"
echo "========================================"
echo ""

# Compute metrics
.venv/bin/python instrumentation/metrics.py logs/
