#!/bin/bash
# JMeter Benchmark — 3 scenarios: 10 / 200 / 1000 req/s
# Usage: ./run-benchmark.sh [10|200|1000|all]
# Requires: brew install jmeter + jp@gc Throughput Shaping Timer plugin

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JMX="$SCRIPT_DIR/hr-agents-load-test.jmx"
REPORTS_DIR="$SCRIPT_DIR/reports"
DATA_DIR="$SCRIPT_DIR/test-data"
BACKEND_HOST="${BACKEND_HOST:-localhost}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

run_scenario() {
    local RPS=$1
    local THREADS=$2
    local RAMPUP=$3
    local DURATION=$4
    local OUT="$REPORTS_DIR/${RPS}rps"

    echo "========================================"
    echo "  Scenario: ${RPS} req/s"
    echo "  Threads: $THREADS | Ramp-up: ${RAMPUP}s | Duration: ${DURATION}s"
    echo "========================================"
    mkdir -p "$OUT/html"

    # Set JVM heap for high-thread scenarios
    if [ "$THREADS" -ge 800 ]; then
        export JVM_ARGS="-Xms2g -Xmx4g"
    fi

    jmeter -n \
        -t "$JMX" \
        -l "$OUT/result.jtl" \
        -e -o "$OUT/html" \
        -Jhost="$BACKEND_HOST" \
        -Jport="$BACKEND_PORT" \
        -Jtarget_rps="$RPS" \
        -Jthreads="$THREADS" \
        -Jrampup="$RAMPUP" \
        -Jduration="$DURATION" \
        -Jdata_dir="$DATA_DIR" \
        2>&1 | tee "$OUT/jmeter.log"

    echo "✅ Report: $OUT/html/index.html"
}

TARGET="${1:-all}"

case "$TARGET" in
    10)
        run_scenario 10 20 30 120
        ;;
    200)
        run_scenario 200 800 60 300
        ;;
    1000)
        run_scenario 1000 2000 60 300
        ;;
    all)
        run_scenario 10   20   30  120
        run_scenario 200  800  60  300
        run_scenario 1000 2000 60  300
        echo ""
        echo "========== ALL SCENARIOS COMPLETE =========="
        echo "Open reports:"
        for rps in 10 200 1000; do
            echo "  open $REPORTS_DIR/${rps}rps/html/index.html"
        done
        ;;
    *)
        echo "Usage: $0 [10|200|1000|all]"
        exit 1
        ;;
esac
