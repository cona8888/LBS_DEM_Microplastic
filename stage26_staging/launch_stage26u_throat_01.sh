#!/usr/bin/env bash
set -u
root=/mnt/c/MATDEM_MICROPLASTIC
config="$root/stage26_designs/stage26u_three_grain_throat_20260820/throat_design_01/config.json"
runner="$root/stage26_staging/run_stage26u_three_grain_throat_v1.py"
out="$root/stage26_runs/stage26u_three_grain_throat_20260820/throat_01"
supervisor="$root/stage26_supervisors/stage26u_three_grain_throat_20260820/throat_01"
if [[ -e "$out" || -e "$supervisor" ]]; then echo "refusing to overwrite immutable output" >&2; exit 73; fi
mkdir -p "$supervisor"
{ echo "config=$config"; echo "config_sha256=$(sha256sum "$config" | awk '{print $1}')";
  echo "runner=$runner"; echo "runner_sha256=$(sha256sum "$runner" | awk '{print $1}')";
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$supervisor/launch_manifest.txt"
STAGE26U_CONFIG="$config" STAGE26U_OUTPUT="$out" /usr/bin/yade -n -x "$runner" > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?; printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
cat "$supervisor/stdout.log"; cat "$supervisor/stderr.log" >&2; echo "CODEX_STAGE26U_EXIT=$code"; exit "$code"
