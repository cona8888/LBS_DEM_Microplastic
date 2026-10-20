#!/usr/bin/env bash
set -euo pipefail

workspace=/mnt/c/MATDEM_MICROPLASTIC
design="$workspace/stage31_designs/stage31b_pore_network_exports_20260826/design_01"
exporter="$workspace/stage26_staging/export_stage26b_revision2_stage25_network_v1.py"
run_root="$workspace/stage31_network_exports/stage31b_pore_network_exports_20260826"
supervisor="$workspace/stage31_supervisors/stage31b_pore_network_exports_20260826/supervisor_01"

if [[ -e "$run_root" || -e "$supervisor" ]]; then
  echo "Refusing to overwrite immutable Stage31b network evidence." >&2
  exit 2
fi
mkdir -p "$(dirname "$run_root")" "$(dirname "$supervisor")"
mkdir "$run_root" "$supervisor"

sha256sum "$design"/*.json "$exporter" "$workspace/stage31_staging/run_stage31b_pore_network_exports_v1.sh" > "$supervisor/input_sha256.tsv"

on_failure() {
  code=$?
  printf 'failed\nexit_code=%s\n' "$code" > "$supervisor/status.txt"
  exit "$code"
}
trap on_failure ERR

for packing in n216_s2 n216_s3; do
  env \
    STAGE26B_R2_NETWORK_CONFIG="$design/${packing}_network_config.json" \
    STAGE26B_R2_NETWORK_OUTPUT="$run_root/$packing" \
    STAGE26B_R2_NETWORK_SCRIPT="$exporter" \
    /usr/bin/yade -n -x "$exporter" \
    > "$supervisor/${packing}.stdout.log" \
    2> "$supervisor/${packing}.stderr.log"
done

printf 'completed\nexit_code=0\n' > "$supervisor/status.txt"

