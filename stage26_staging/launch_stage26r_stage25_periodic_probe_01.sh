#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/MATDEM_MICROPLASTIC
if ps -eo args | grep -E '[/]usr/bin/yade -n -x' >/dev/null; then
    echo "STAGE26R_REFUSAL=another_yade_batch_is_active" >&2
    exit 73
fi
STAGE26R_STATE="$root/stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_04/mu_0.60/load_bearing_state.yade.gz" \
STAGE26R_STATE_SHA256="598107294f82d3a5f317f02fc87599d324fc614bb02bfd5048f6a932cced4aad" \
STAGE26R_OUTPUT="$root/stage26_runs/stage26r_periodic_radius_restoration_20260819/stage25_state_probe_01" \
/usr/bin/yade -n -x "$root/stage26_staging/probe_stage26r_stage25_periodic_state_v1.py"
