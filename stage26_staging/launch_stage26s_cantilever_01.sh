#!/usr/bin/env bash
set -u

root=/mnt/c/MATDEM_MICROPLASTIC
config="$root/stage26_designs/stage26s_flexible_fibre_cantilever_20260819/clean_design_01/config.json"
runner="$root/stage26_staging/run_stage26s_flexible_fibre_cantilever_v1.py"
out="$root/stage26_runs/stage26s_flexible_fibre_cantilever_20260819/cantilever_01"
supervisor="$root/stage26_supervisors/stage26s_flexible_fibre_cantilever_20260819/cantilever_01"

if [[ -e "$out" || -e "$supervisor" ]]; then
  echo "refusing to overwrite immutable output" >&2
  exit 73
fi
mkdir -p "$supervisor"
{
  echo "config=$config"
  echo "config_sha256=$(sha256sum "$config" | awk '{print $1}')"
  echo "runner=$runner"
  echo "runner_sha256=$(sha256sum "$runner" | awk '{print $1}')"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$supervisor/launch_manifest.txt"

STAGE26S_CONFIG="$config" STAGE26S_OUTPUT="$out" /usr/bin/yade -n -x "$runner" \
  > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?
printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
cat "$supervisor/stdout.log"
cat "$supervisor/stderr.log" >&2
echo "CODEX_STAGE26S_EXIT=$code"
exit "$code"
