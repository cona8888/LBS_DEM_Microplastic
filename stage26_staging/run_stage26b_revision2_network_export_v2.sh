#!/usr/bin/env bash
set -euo pipefail

project=/mnt/c/MATDEM_MICROPLASTIC
config="$project/stage26_staging/stage26b_revision2_network_export_execution_v2.json"
script="$project/stage26_staging/export_stage26b_revision2_stage25_network_v1.py"
output="$project/stage26_network_exports/stage26b_revision2_stage25_network_20260816/export_02"

if [[ -e "$output" ]]; then
  echo "Refusing to overwrite immutable network-export output: $output" >&2
  exit 73
fi

cd "$project"
exec env \
  STAGE26B_R2_NETWORK_CONFIG="$config" \
  STAGE26B_R2_NETWORK_OUTPUT="$output" \
  STAGE26B_R2_NETWORK_SCRIPT="$script" \
  /usr/bin/yade -n -x "$script"
