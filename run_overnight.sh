#!/bin/bash
# Overnight experiment runner
# Runs DeepSeek R1 14B and 70B on login_cipher after current experiments finish
# Started: $(date)

set -e

CHALLENGE="login_cipher"
STEPS=20
RUNS=3

echo "========================================"
echo "OVERNIGHT EXPERIMENTS"
echo "Challenge: $CHALLENGE"
echo "Models: R1 14B, R1 70B"
echo "Started: $(date)"
echo "========================================"

# --- R1 14B on login_cipher ---
echo ""
echo "======== R1 14B: login_cipher ========"
CONFIG="llm.config.server"
for LABEL in A B C D E; do
  case $LABEL in
    A) FLAGS="--interventions none" ;;
    B) FLAGS="--interventions light" ;;
    C) FLAGS="--structured --interventions none" ;;
    D) FLAGS="--structured --interventions light" ;;
    E) FLAGS="--structured --interventions strong" ;;
  esac
  for i in $(seq 1 $RUNS); do
    echo ">>> R1-14B $LABEL run $i/$RUNS ($(date +%H:%M))"
    .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "r1_14b_lc_${LABEL}_${i}" 2>&1 | tail -3
    echo ""
  done
done
echo "======== R1 14B: login_cipher COMPLETE $(date) ========"

# --- R1 70B on login_cipher ---
echo ""
echo "======== R1 70B: login_cipher ========"
CONFIG="llm.config.r1-70b"
for LABEL in A B C D E; do
  case $LABEL in
    A) FLAGS="--interventions none" ;;
    B) FLAGS="--interventions light" ;;
    C) FLAGS="--structured --interventions none" ;;
    D) FLAGS="--structured --interventions light" ;;
    E) FLAGS="--structured --interventions strong" ;;
  esac
  for i in $(seq 1 $RUNS); do
    echo ">>> R1-70B $LABEL run $i/$RUNS ($(date +%H:%M))"
    .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "r1_70b_lc_${LABEL}_${i}" 2>&1 | tail -3
    echo ""
  done
done
echo "======== R1 70B: login_cipher COMPLETE $(date) ========"

# --- Also run R1 70B on yurisimplekeygen (clean 20-step run) ---
echo ""
echo "======== R1 70B: yurisimplekeygen ========"
CHALLENGE2="yurisimplekeygen"
for LABEL in A B C D E; do
  case $LABEL in
    A) FLAGS="--interventions none" ;;
    B) FLAGS="--interventions light" ;;
    C) FLAGS="--structured --interventions none" ;;
    D) FLAGS="--structured --interventions light" ;;
    E) FLAGS="--structured --interventions strong" ;;
  esac
  for i in $(seq 1 $RUNS); do
    echo ">>> R1-70B $LABEL run $i/$RUNS ($(date +%H:%M))"
    .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE2 $FLAGS --steps $STEPS --run-id "r1_70b_ysk_${LABEL}_${i}" 2>&1 | tail -3
    echo ""
  done
done
echo "======== R1 70B: yurisimplekeygen COMPLETE $(date) ========"

echo ""
echo "========================================"
echo "ALL OVERNIGHT EXPERIMENTS COMPLETE"
echo "Finished: $(date)"
echo "========================================"
