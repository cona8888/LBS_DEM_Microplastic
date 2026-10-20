#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/MATDEM_MICROPLASTIC
if ps -eo args | grep -E '[/]usr/bin/yade -n -x' >/dev/null; then
    echo "STAGE26R_SMOKE_REFUSAL=another_yade_batch_is_active" >&2
    exit 73
fi
STAGE26R_SMOKE_CONFIG="$root/stage26_designs/stage26r_periodic_radius_restoration_20260819/clean_design_02/config.json" \
STAGE26R_SMOKE_OUTPUT="$root/stage26_runs/stage26r_periodic_radius_restoration_20260819/fixed_cell_smoke_02" \
STAGE26R_SMOKE_SCRIPT="$root/stage26_staging/run_stage26r_fixed_cell_smoke_v1.py" \
/usr/bin/yade -n -x "$root/stage26_staging/run_stage26r_fixed_cell_smoke_v1.py"
