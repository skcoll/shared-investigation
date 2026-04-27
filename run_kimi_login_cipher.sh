#!/bin/bash
set -e
export KIMI_API_KEY="sk-HnoCM3euRWEioWZZfu1IJZqZ7TwXE7uNe0TggIi71ovP2Xyj"

CHALLENGE="login_cipher"
STEPS=20
CONFIG="llm.config.kimi"
RUNS=3

echo "========================================"
echo "Kimi K2: login_cipher"
echo "Conditions: 5 (A-E) x $RUNS runs = $((5 * RUNS)) total"
echo "Budget: $STEPS steps per run"
echo "========================================"
echo ""

for LABEL in A B C D E; do
  case $LABEL in
    A) FLAGS="--interventions none" ;;
    B) FLAGS="--interventions light" ;;
    C) FLAGS="--structured --interventions none" ;;
    D) FLAGS="--structured --interventions light" ;;
    E) FLAGS="--structured --interventions strong" ;;
  esac
  for i in $(seq 1 $RUNS); do
    echo ">>> Kimi $LABEL run $i/$RUNS"
    .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "kimi_lc_${LABEL}_${i}" 2>&1 | tail -5
    echo ""
  done
done

echo "========================================"
echo "login_cipher KIMI COMPLETE"
echo "========================================"
