#!/bin/bash

set -e
set -u

OUT_DIR=out
mkdir -p $OUT_DIR
cp tools/build.ninja $OUT_DIR
ninja -C out
