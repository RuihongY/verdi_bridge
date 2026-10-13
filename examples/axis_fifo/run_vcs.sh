#!/usr/bin/env bash
set -euo pipefail
# Set up your licensed VCS environment before running this script.
root=$(cd "$(dirname "$0")/../.." && pwd)
build=${1:-"$root/build/axis_fifo"}
build=$(cd "$build" && pwd)
for case in baseline stalled_read_pointer wrong_full_compare; do
  (
    cd "$build/$case"
    vcs -full64 -sverilog axis_fifo.v "$root/examples/axis_fifo/tb.sv" -top tb -o simv >compile.log 2>&1
    for seed in 1 7 42; do
      mkdir -p "seed-$seed"
      (cd "seed-$seed" && ../simv +SEED="$seed" >sim.log 2>&1)
    done
  )
done
python3 "$root/examples/axis_fifo/check_results.py" "$build"
