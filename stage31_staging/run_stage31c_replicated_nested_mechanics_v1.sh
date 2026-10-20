#!/usr/bin/env bash
set -euo pipefail
export STAGE31C_CONFIG=/mnt/c/MATDEM_MICROPLASTIC/stage31_designs/stage31c_replicated_nested_mechanics_20260826/mechanics_preflight_01/config.json
export STAGE31C_HANDOFF=/mnt/c/MATDEM_MICROPLASTIC/stage31_evaluations/stage31c_replicated_nested_mechanics_20260826/mechanics_release_01/handoff.json
export STAGE31C_OUTPUT=/mnt/c/MATDEM_MICROPLASTIC/stage31_runs/stage31c_replicated_nested_mechanics_20260826/mechanics_01
exec /usr/bin/yade -n -x /mnt/c/MATDEM_MICROPLASTIC/stage31_staging/run_stage31c_replicated_nested_mechanics_v1.py
