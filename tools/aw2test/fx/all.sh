#!/bin/sh
# usage: fx/all.sh MODE SCENE...   (runs the scenes four at a time)
mode=$1; shift
cd "$(dirname "$0")/.."
printf '%s\n' "$@" | xargs -P 4 -I{} sh -c "python3 fx/run.py {} $mode out_ovl/fx > out_ovl/fx/{}.$mode.out 2>&1"
