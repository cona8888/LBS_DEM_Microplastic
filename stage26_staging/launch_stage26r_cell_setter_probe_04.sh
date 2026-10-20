#!/usr/bin/env bash
set -eu

state='/mnt/c/MATDEM_MICROPLASTIC/stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_04/mu_0.60/load_bearing_state.yade.gz'
output='/mnt/c/MATDEM_MICROPLASTIC/stage26_runs/stage26r_periodic_radius_restoration_20260819/cell_setter_probe_04/probe.json'
script='/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/probe_stage26r_cell_setters_v1.py'

mkdir -p "$(dirname "$output")"
STAGE26R_CELL_SETTER_STATE="$state" \
STAGE26R_CELL_SETTER_OUTPUT="$output" \
/usr/bin/yade -n -x "$script"
