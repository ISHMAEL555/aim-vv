#!/usr/bin/env bash
# Phase 4 gate: strict build, gcc analyzer, tests on a coverage build, and a
# 100% line+branch coverage requirement. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"

echo "== strict build (-Wconversion -Wshadow ... -Werror)"
cmake -S . -B build-strict -DAIM_STRICT=ON >/dev/null
cmake --build build-strict

echo "== gcc -fanalyzer"
for f in src/*.c target/aim_target/framer.c; do gcc -std=c99 -fanalyzer -Wall -Wextra -Werror -c "$f" -o /dev/null; done

echo "== tests on coverage build"
cmake -S . -B build-cov -DAIM_COVERAGE=ON -DCMAKE_BUILD_TYPE=Debug >/dev/null
cmake --build build-cov
find build-cov -name '*.gcda' -delete
AIM_LIB="$PWD/build-cov/libaim.so" AIM_FRAMER_LIB="$PWD/build-cov/libaimframer.so" "$PY" -m pytest tests -q

echo "== coverage gate (100% line and branch)"
mkdir -p build-cov/report
"$PY" -m gcovr -r . --object-directory build-cov --filter 'src/' --filter 'target/aim_target/framer.c' \
    --fail-under-line 100 --fail-under-branch 100 \
    --txt --html-details build-cov/report/index.html
