#!/usr/bin/env bash
set -euo pipefail

root=/mnt/c/MATDEM_MICROPLASTIC
config="$root/stage26_designs/stage26q_density_geometry_flexure_20260818/clean_density_controller_design_03/config.json"
runner="$root/stage26_staging/run_stage26q_clean_density_controller_v1.py"
output="$root/stage26_runs/stage26q_density_geometry_flexure_20260818/clean_density_controller_03"
supervisor="$root/stage26_supervisors/stage26q_density_geometry_flexure_20260818/clean_density_controller_03"

if ps -eo args | grep -E '[/]usr/bin/yade -n -x' >/dev/null; then
    echo "STAGE26Q_REFUSAL=another_yade_batch_is_active" >&2
    exit 73
fi
if [[ -e "$output" || -e "$supervisor" ]]; then
    echo "STAGE26Q_REFUSAL=immutable_output_or_supervisor_exists" >&2
    exit 74
fi

mkdir -p "$supervisor"
{
    printf 'timestamp_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'config=%s\n' "$config"
    printf 'config_sha256=%s\n' "$(sha256sum "$config" | awk '{print $1}')"
    printf 'runner=%s\n' "$runner"
    printf 'runner_sha256=%s\n' "$(sha256sum "$runner" | awk '{print $1}')"
    printf 'output=%s\n' "$output"
    printf 'yade=%s\n' "$(command -v yade)"
    printf 'yade_version=%s\n' "$(yade --version 2>&1 | head -1)"
} > "$supervisor/launch_manifest.txt"

set +e
STAGE26Q_CONFIG="$config" \
STAGE26Q_OUTPUT="$output" \
STAGE26Q_SCRIPT="$runner" \
/usr/bin/yade -n -x "$runner" > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?
set -e
printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
printf 'STAGE26Q_RUNNER_EXIT=%s\n' "$code"
exit "$code"
