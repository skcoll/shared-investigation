#!/bin/bash
# Master experiment script — all models, all challenges, full traces
# Kimi runs are in a separate script to run concurrently

set -e
STEPS=20
RUNS=3

run_model() {
    local CONFIG=$1
    local MODEL_TAG=$2
    local CHALLENGE=$3

    for LABEL in A B C D E; do
        case $LABEL in
            A) FLAGS="--interventions none" ;;
            B) FLAGS="--interventions light" ;;
            C) FLAGS="--structured --interventions none" ;;
            D) FLAGS="--structured --interventions light" ;;
            E) FLAGS="--structured --interventions strong" ;;
        esac
        for i in $(seq 1 $RUNS); do
            echo ">>> ${MODEL_TAG} ${CHALLENGE} ${LABEL} run ${i}/${RUNS} ($(date +%H:%M))"
            .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "${MODEL_TAG}_${CHALLENGE:0:3}_${LABEL}_${i}" 2>&1 | tail -3
            echo ""
        done
    done
}

echo "========================================"
echo "FULL EXPERIMENT SUITE (DeepSeek models)"
echo "Started: $(date)"
echo "========================================"

echo ""
echo "===== R1 14B: yurisimplekeygen ====="
run_model "llm.config.server" "r1_14b" "yurisimplekeygen"

echo ""
echo "===== R1 14B: login_cipher ====="
run_model "llm.config.server" "r1_14b" "login_cipher"

echo ""
echo "===== R1 70B: yurisimplekeygen ====="
run_model "llm.config.r1-70b" "r1_70b" "yurisimplekeygen"

echo ""
echo "===== R1 70B: login_cipher ====="
run_model "llm.config.r1-70b" "r1_70b" "login_cipher"

echo ""
echo "========================================"
echo "DeepSeek COMPLETE: $(date)"
echo "========================================"
