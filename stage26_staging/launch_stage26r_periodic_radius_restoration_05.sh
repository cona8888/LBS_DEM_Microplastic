#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/MATDEM_MICROPLASTIC
config="$root/stage26_designs/stage26r_periodic_radius_restoration_20260819/clean_design_05/config.json"
runner="$root/stage26_staging/run_stage26r_periodic_radius_restoration_v3.py"
output="$root/stage26_runs/stage26r_periodic_radius_restoration_20260819/clean_radius_restoration_05"
supervisor="$root/stage26_supervisors/stage26r_periodic_radius_restoration_20260819/clean_radius_restoration_05"
if ps -eo args | grep -E '[/]usr/bin/yade -n -x' >/dev/null; then
    echo "STAGE26R_REFUSAL=another_yade_batch_is_active" >&2
    exit 73
fi
if [[ -e "$output" || -e "$supervisor" ]]; then
    echo "STAGE26R_REFUSAL=immutable_output_or_supervisor_exists" >&2
    exit 74
fi
mkdir -p "$supervisor"
{
    printf 'timestamp_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'config_sha256=%s\n' "$(sha256sum "$config" | awk '{print $1}')"
    printf 'runner_sha256=%s\n' "$(sha256sum "$runner" | awk '{print $1}')"
    printf 'fixed_cell_smoke_sha256=%s\n' "$(sha256sum "$root/stage26_runs/stage26r_periodic_radius_restoration_20260819/fixed_cell_smoke_04/result.json" | awk '{print $1}')"
    printf 'output=%s\n' "$output"
    printf 'yade_version=%s\n' "$(yade --version 2>&1 | head -1)"
} > "$supervisor/launch_manifest.txt"
set +e
STAGE26R_CONFIG="$config" STAGE26R_OUTPUT="$output" STAGE26R_SCRIPT="$runner" \
/usr/bin/yade -n -x "$runner" > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?
set -e
printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
printf 'STAGE26R_RUNNER_EXIT=%s\n' "$code"
exit "$code"
