#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/MATDEM_MICROPLASTIC
if ps -eo args | grep -E '[/]usr/bin/yade -n -x' >/dev/null; then
    echo "STAGE26Q_SMOKE_REFUSAL=another_yade_batch_is_active" >&2
    exit 73
fi
STAGE26Q_SMOKE_CONFIG="$root/stage26_designs/stage26q_density_geometry_flexure_20260818/clean_density_controller_design_02/config.json" \
STAGE26Q_SMOKE_OUTPUT="$root/stage26_runs/stage26q_density_geometry_flexure_20260818/negative_sign_smoke_02" \
STAGE26Q_SMOKE_SCRIPT="$root/stage26_staging/run_stage26q_negative_strain_sign_smoke_v1.py" \
/usr/bin/yade -n -x "$root/stage26_staging/run_stage26q_negative_strain_sign_smoke_v1.py"
