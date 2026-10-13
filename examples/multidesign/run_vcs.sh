#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
build=${1:-"$root/build/multidesign"}
shift || true
build=$(cd "$build" && pwd)
variants=("$@")
if [ ${#variants[@]} -eq 0 ]; then variants=(baseline mutant); fi
for design in uart axil arbiter; do
  for variant in "${variants[@]}"; do
    (
      cd "$build/$design/$variant"
      vcs -full64 -sverilog ./*.v "$root/examples/multidesign/${design}_tb.sv" -top tb -o simv >compile.log 2>&1
      for seed in 1 7 42; do
        mkdir -p "seed-$seed"
        (cd "seed-$seed" && ../simv +SEED="$seed" >sim.log 2>&1)
      done
    )
  done
done
