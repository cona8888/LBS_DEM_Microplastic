#!/usr/bin/env bash
set -eu

config='/mnt/c/MATDEM_MICROPLASTIC/stage26_designs/stage26r_periodic_radius_restoration_20260819/clean_design_04/config.json'
output='/mnt/c/MATDEM_MICROPLASTIC/stage26_runs/stage26r_periodic_radius_restoration_20260819/fixed_cell_smoke_04'
script='/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26r_fixed_cell_smoke_v3.py'

STAGE26R_SMOKE_CONFIG="$config" \
STAGE26R_SMOKE_OUTPUT="$output" \
STAGE26R_SMOKE_SCRIPT="$script" \
/usr/bin/yade -n -x "$script"
