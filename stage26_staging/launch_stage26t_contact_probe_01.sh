#!/usr/bin/env bash
set -euo pipefail
root=/mnt/c/MATDEM_MICROPLASTIC
out="$root/stage26_runs/stage26t_sand_fibre_contact_20260820/contact_probe_01"
script="$root/stage26_staging/probe_stage26t_sphere_grid_contact_v1.py"
if [[ -e "$out" ]]; then echo "refusing to overwrite $out" >&2; exit 73; fi
STAGE26T_OUTPUT="$out" /usr/bin/yade -n -x "$script"
