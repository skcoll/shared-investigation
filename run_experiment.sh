#!/bin/bash
set -e

CHALLENGE="yurisimplekeygen"
STEPS=15
CONFIG="llm.config.server"

echo "========================================"
echo "FULL EXPERIMENT: $CHALLENGE"
echo "5 conditions x 3 runs = 15 total runs"
echo "========================================"

# Condition A: baseline, no interventions
for i in 1 2 3; do
  echo ""
  echo ">>> Condition A (baseline/none) - Run $i"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --interventions none --steps $STEPS --run-id "A_${i}" 2>&1 | tail -3
done

# Condition B: baseline, light interventions
for i in 1 2 3; do
  echo ""
  echo ">>> Condition B (baseline/light) - Run $i"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --interventions light --steps $STEPS --run-id "B_${i}" 2>&1 | tail -3
done

# Condition C: structured, no interventions
for i in 1 2 3; do
  echo ""
  echo ">>> Condition C (structured/none) - Run $i"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --structured --interventions none --steps $STEPS --run-id "C_${i}" 2>&1 | tail -3
done

# Condition D: structured, light interventions
for i in 1 2 3; do
  echo ""
  echo ">>> Condition D (structured/light) - Run $i"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --structured --interventions light --steps $STEPS --run-id "D_${i}" 2>&1 | tail -3
done

# Condition E: structured, strong interventions
for i in 1 2 3; do
  echo ""
  echo ">>> Condition E (structured/strong) - Run $i"
  .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE --structured --interventions strong --steps $STEPS --run-id "E_${i}" 2>&1 | tail -3
done

echo ""
echo "========================================"
echo "ALL RUNS COMPLETE"
echo "========================================"

# Compute metrics
echo ""
.venv/bin/python instrumentation/metrics.py logs/
