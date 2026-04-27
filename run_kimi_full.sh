#!/bin/bash
set -e
export KIMI_API_KEY="sk-HnoCM3euRWEioWZZfu1IJZqZ7TwXE7uNe0TggIi71ovP2Xyj"
CHALLENGE="yurisimplekeygen"
STEPS=20
CONFIG="llm.config.kimi"
for LABEL in A B C D E; do
  case $LABEL in
    A) FLAGS="--interventions none" ;;
    B) FLAGS="--interventions light" ;;
    C) FLAGS="--structured --interventions none" ;;
    D) FLAGS="--structured --interventions light" ;;
    E) FLAGS="--structured --interventions strong" ;;
  esac
  for i in 1 2 3; do
    echo ">>> Kimi $LABEL run $i"
    .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "kimi_${LABEL}_${i}" 2>&1 | tail -3
    echo ""
  done
done
echo "=== KIMI COMPLETE ==="
