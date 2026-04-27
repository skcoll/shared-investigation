#!/bin/bash
set -e
STEPS=20
CONFIG="llm.config.r1-70b"
RUNS=3

echo "========================================"
echo "R1 70B: BOTH CHALLENGES"
echo "Started: $(date)"
echo "========================================"

for CHALLENGE in yurisimplekeygen login_cipher; do
  echo ""
  echo "======== R1 70B: $CHALLENGE ========"
  for LABEL in A B C D E; do
    case $LABEL in
      A) FLAGS="--interventions none" ;;
      B) FLAGS="--interventions light" ;;
      C) FLAGS="--structured --interventions none" ;;
      D) FLAGS="--structured --interventions light" ;;
      E) FLAGS="--structured --interventions strong" ;;
    esac
    for i in $(seq 1 $RUNS); do
      echo ">>> R1-70B $CHALLENGE $LABEL run $i/$RUNS ($(date +%H:%M))"
      .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "r1_70b_${CHALLENGE:0:3}_${LABEL}_${i}" 2>&1 | tail -3
      echo ""
    done
  done
  echo "======== R1 70B: $CHALLENGE COMPLETE $(date) ========"
done

echo ""
echo "========================================"
echo "ALL R1 70B COMPLETE: $(date)"
echo "========================================"
