#!/usr/bin/env bash
set -u

root=/mnt/c/MATDEM_MICROPLASTIC
config="$root/stage26_designs/stage26w_dense_wall_shrink_regrow_20260823/design_01/config.json"
runner="$root/stage26_staging/run_stage26w_dense_wall_shrink_regrow_v1.py"
output="$root/stage26_runs/stage26w_dense_wall_shrink_regrow_20260823/pilot_01"
supervisor="$root/stage26_supervisors/stage26w_dense_wall_shrink_regrow_20260823/pilot_01"

if [ -e "$output" ] || [ -e "$supervisor" ]; then
  echo "immutable Stage26w output or supervisor already exists" >&2
  exit 73
fi
mkdir -p "$supervisor"
{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "pwd=$(pwd)"
  echo "config_sha256=$(sha256sum "$config" | awk '{print $1}')"
  echo "runner_sha256=$(sha256sum "$runner" | awk '{print $1}')"
  echo "command=/usr/bin/yade -n -x $runner"
} > "$supervisor/launch_manifest.txt"

STAGE26W_CONFIG="$config" \
STAGE26W_OUTPUT="$output" \
STAGE26W_SCRIPT="$runner" \
/usr/bin/yade -n -x "$runner" > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?
printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
cat "$supervisor/stdout.log"
if [ -s "$supervisor/stderr.log" ]; then
  cat "$supervisor/stderr.log" >&2
fi
exit "$code"
