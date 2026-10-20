#!/usr/bin/env bash
set -euo pipefail

workspace=/mnt/c/MATDEM_MICROPLASTIC
design="$workspace/stage31_designs/stage31a_packing_replication_bridge_20260826/design_01"
runner="$workspace/stage25_staging/stage25a_yade_pure_sand_mechanics_v1.py"
run_root="$workspace/stage31_runs/stage31a_packing_replication_bridge_20260826"
supervisor="$workspace/stage31_supervisors/stage31a_packing_replication_bridge_20260826/supervisor_01"

if [[ -e "$run_root" || -e "$supervisor" ]]; then
  echo "Refusing to overwrite immutable Stage31a output or supervisor evidence." >&2
  exit 2
fi

mkdir -p "$(dirname "$run_root")" "$(dirname "$supervisor")"
mkdir "$run_root" "$supervisor"

sha256sum \
  "$workspace/stage31_staging/STAGE31A_PACKING_REPLICATION_BRIDGE_CONTRACT.md" \
  "$workspace/stage31_staging/run_stage31a_packing_replication_bridge_v1.sh" \
  "$design/manifest.json" \
  "$design/n216_s2_config.json" \
  "$design/n216_s3_config.json" \
  "$runner" > "$supervisor/input_sha256.tsv"

on_failure() {
  code=$?
  printf 'failed\nexit_code=%s\n' "$code" > "$supervisor/status.txt"
  exit "$code"
}
trap on_failure ERR

for packing in n216_s2 n216_s3; do
  config="$design/${packing}_config.json"
  output="$run_root/${packing}_qualification_01"
  env \
    STAGE25_CONFIG="$config" \
    STAGE25_OUTPUT="$output" \
    STAGE25_SCRIPT="$runner" \
    /usr/bin/yade -n -x "$runner" \
    > "$supervisor/${packing}.stdout.log" \
    2> "$supervisor/${packing}.stderr.log"
done

printf 'completed\nexit_code=0\n' > "$supervisor/status.txt"

