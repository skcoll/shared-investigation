#!/bin/bash
# Kimi K2 experiments — runs concurrently with DeepSeek via different API
set -e
export KIMI_API_KEY="sk-HnoCM3euRWEioWZZfu1IJZqZ7TwXE7uNe0TggIi71ovP2Xyj"
STEPS=20
RUNS=3
CONFIG="llm.config.kimi"

run_challenge() {
    local CHALLENGE=$1
    for LABEL in A B C D E; do
        case $LABEL in
            A) FLAGS="--interventions none" ;;
            B) FLAGS="--interventions light" ;;
            C) FLAGS="--structured --interventions none" ;;
            D) FLAGS="--structured --interventions light" ;;
            E) FLAGS="--structured --interventions strong" ;;
        esac
        for i in $(seq 1 $RUNS); do
            echo ">>> Kimi ${CHALLENGE} ${LABEL} run ${i}/${RUNS} ($(date +%H:%M))"
            .venv/bin/python -u agent/loop.py --config $CONFIG --challenge $CHALLENGE $FLAGS --steps $STEPS --run-id "kimi_${CHALLENGE:0:3}_${LABEL}_${i}" 2>&1 | tail -3
            echo ""
        done
    done
}

echo "========================================"
echo "KIMI K2: ALL CHALLENGES"
echo "Started: $(date)"
echo "========================================"

echo ""
echo "===== Kimi: yurisimplekeygen ====="
run_challenge "yurisimplekeygen"

echo ""
echo "===== Kimi: login_cipher ====="
run_challenge "login_cipher"

echo ""
echo "========================================"
echo "KIMI COMPLETE: $(date)"
echo "========================================"
