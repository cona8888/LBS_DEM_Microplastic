#!/usr/bin/env bash
set -euo pipefail

export STAGE28A_CONFIG=/mnt/c/MATDEM_MICROPLASTIC/stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_01/config.json
export STAGE28A_HANDOFF=/mnt/c/MATDEM_MICROPLASTIC/stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/execution_audit_01/execution_handoff.json
export STAGE28A_OUTPUT=/mnt/c/MATDEM_MICROPLASTIC/stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_01

exec /usr/bin/yade -n -x /mnt/c/MATDEM_MICROPLASTIC/stage28_staging/run_stage28a_two_fibre_mechanics_v1.py
