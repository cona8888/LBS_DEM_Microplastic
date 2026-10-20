#!/usr/bin/env bash
set -u
root=/mnt/c/MATDEM_MICROPLASTIC
config="$root/stage26_designs/stage26x_periodic_pore_geometry_20260823/fixed_sand_design_02/config.json"
runner="$root/stage26_staging/run_stage26x_periodic_fixed_sand_fibre_v2.py"
output="$root/stage26_runs/stage26x_periodic_pore_geometry_20260823/fixed_sand_pilot_02"
supervisor="$root/stage26_supervisors/stage26x_periodic_pore_geometry_20260823/fixed_sand_pilot_02"
if [ -e "$output" ] || [ -e "$supervisor" ]; then echo "immutable Stage26x v2 path exists" >&2; exit 73; fi
mkdir -p "$supervisor"
{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "config_sha256=$(sha256sum "$config" | awk '{print $1}')"
  echo "runner_sha256=$(sha256sum "$runner" | awk '{print $1}')"
} > "$supervisor/launch_manifest.txt"
STAGE26X_CONFIG="$config" STAGE26X_OUTPUT="$output" /usr/bin/yade -n -x "$runner" > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?
printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
cat "$supervisor/stdout.log"
if [ -s "$supervisor/stderr.log" ]; then cat "$supervisor/stderr.log" >&2; fi
exit "$code"
