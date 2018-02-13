#!/bin/bash

set -e
set -u

OUT_DIR=out
mkdir -p $OUT_DIR

OUTPUT_SRC=$OUT_DIR/generated.cc
OUTPUT_BIN=$OUT_DIR/generated

echo "=== Generating ==="
./sc.py --root lang/scale/playground --module main --out $OUTPUT_SRC
cat $OUTPUT_SRC

echo
echo "=== Compiling ==="
FLAGS="-std=c++14"
FLAGS+=" -O1"
#FLAGS+=" -O2 -flto"
#FLAGS+=" -fno-asynchronous-unwind-tables -fno-exceptions -fno-rtti -fno-math-errno -fmerge-all-constants -fno-ident"
FLAGS+=" -fsanitize=address -fno-omit-frame-pointer"
clang $FLAGS $OUTPUT_SRC libscale/runtime.cc -o $OUTPUT_BIN

echo
echo "=== Running ==="
$OUTPUT_BIN
