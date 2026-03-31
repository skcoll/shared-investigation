#!/bin/bash
set -e

CHALLENGE="yurisimplekeygen"
STEPS=20
CONFIG="llm.config.r1-70b"
RUNS=3

echo "========================================"
echo "DeepSeek R1 70B EXPERIMENT"
echo "Challenge: $CHALLENGE"
echo "Conditions: 5 (A-E) x $RUNS runs = $((5 * RUNS)) total"
echo "Budget: $STEPS steps per run"
echo "========================================"
echo ""

for COND_LABEL in A B C D E; do
  case $COND_LABEL in
    A) FLAGS="--interventions none" ;;
    B) FLAGS="--interventions light" ;;
    C) FLAGS="--structured --interventions none" ;;
    D) FLAGS="--structured --interventions light" ;;
    E) FLAGS="--structured --interventions strong" ;;
  esac

  for i in $(seq 1 $RUNS); do
    echo ">>> Condition $COND_LABEL - Run $i/$RUNS"
    .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "${COND_LABEL}_${i}" 2>&1 | tail -5
    echo ""
  done
done

echo "========================================"
echo "ALL RUNS COMPLETE"
echo "========================================"
echo ""

.venv/bin/python instrumentation/metrics.py logs/
