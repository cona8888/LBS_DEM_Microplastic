#!/usr/bin/env bash
set -u
root=/mnt/c/MATDEM_MICROPLASTIC
config="$root/stage26_designs/stage26v_216_flexible_fibre_integration_20260823/fixed_sand_design_01/config.json"
runner="$root/stage26_staging/run_stage26v_fixed_sand_flexible_pilot_v1.py"
out="$root/stage26_runs/stage26v_216_flexible_fibre_integration_20260823/fixed_sand_pilot_01"
supervisor="$root/stage26_supervisors/stage26v_216_flexible_fibre_integration_20260823/fixed_sand_pilot_01"
if [[ -e "$out" || -e "$supervisor" ]]; then echo "refusing to overwrite immutable output" >&2; exit 73; fi
mkdir -p "$supervisor"
{
  echo "config=$config"
  echo "config_sha256=$(sha256sum "$config" | awk '{print $1}')"
  echo "runner=$runner"
  echo "runner_sha256=$(sha256sum "$runner" | awk '{print $1}')"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$supervisor/launch_manifest.txt"
STAGE26V_CONFIG="$config" STAGE26V_OUTPUT="$out" /usr/bin/yade -n -x "$runner" > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?
printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
cat "$supervisor/stdout.log"
cat "$supervisor/stderr.log" >&2
echo "CODEX_STAGE26V_FIXED_SAND_EXIT=$code"
exit "$code"
