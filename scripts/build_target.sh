#!/usr/bin/env bash
# Compile the Phase 7 firmware for the Arduino UNO and fail on any warning
# originating in our code (src/ or target/). This is the only check that
# exercises 16-bit-int semantics; the host build cannot catch those bugs.
set -euo pipefail
cd "$(dirname "$0")/../target"
BUILD="$(mktemp -d)"; LOGDIR="$(mktemp -d)"; trap 'rm -rf "$BUILD" "$LOGDIR"' EXIT
arduino-cli compile --clean --fqbn arduino:avr:uno aim_target --warnings all \
    --build-path "$BUILD" 2>&1 | tee "$LOGDIR/log.txt"
if grep -E "(^|/)(aim_target/(src/|framer|aim_target\.ino))[^ ]*: *(warning|error)" "$LOGDIR/log.txt" \
   || grep -E "^/.*aim-vv/.*(warning|error):" "$LOGDIR/log.txt" | grep -v ".arduino15"; then
    echo "FAIL: warnings in project code for AVR target" >&2; exit 1
fi
echo "target build OK (no project warnings)"
