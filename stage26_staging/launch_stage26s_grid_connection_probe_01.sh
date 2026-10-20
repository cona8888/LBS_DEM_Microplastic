#!/usr/bin/env bash
set -euo pipefail

root=/mnt/c/MATDEM_MICROPLASTIC
out="$root/stage26_runs/stage26s_flexible_fibre_cantilever_20260819/grid_connection_probe_01"
script="$root/stage26_staging/probe_stage26s_grid_connection_stiffness_v1.py"

if [[ -e "$out" ]]; then
  echo "refusing to overwrite $out" >&2
  exit 73
fi

STAGE26S_OUTPUT="$out" /usr/bin/yade -n -x "$script"
