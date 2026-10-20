#!/usr/bin/env bash
set -u
root=/mnt/c/MATDEM_MICROPLASTIC
state="$root/stage26_runs/stage26o_gravity_joint_deposition_20260818/clean_control_13/qualified_clean_sand_wall_state.yade.gz"
checkpoint="$root/stage26_checkpoints/stage26o_gravity_joint_deposition_20260818/clean_control_acceptance_13/checkpoint_manifest.json"
script="$root/stage26_staging/probe_stage26v_stage26o_geometry_v1.py"
out="$root/stage26_runs/stage26v_216_flexible_fibre_integration_20260823/geometry_export_01"
supervisor="$root/stage26_supervisors/stage26v_216_flexible_fibre_integration_20260823/geometry_export_01"
state_sha=809632150c383fc9deca2dfa76e012e05be12cb7415112c848663b5def49867f
checkpoint_sha=33862624a4cf62be9777d02e89749d29383eca592145e8b88ae42ed5f2db340f
if [[ -e "$out" || -e "$supervisor" ]]; then echo "refusing to overwrite immutable output" >&2; exit 73; fi
mkdir -p "$supervisor"
{
  echo "state=$state"
  echo "state_sha256=$(sha256sum "$state" | awk '{print $1}')"
  echo "checkpoint=$checkpoint"
  echo "checkpoint_sha256=$(sha256sum "$checkpoint" | awk '{print $1}')"
  echo "probe=$script"
  echo "probe_sha256=$(sha256sum "$script" | awk '{print $1}')"
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$supervisor/launch_manifest.txt"
STAGE26V_SOURCE_STATE="$state" \
STAGE26V_SOURCE_STATE_SHA256="$state_sha" \
STAGE26V_SOURCE_CHECKPOINT="$checkpoint" \
STAGE26V_SOURCE_CHECKPOINT_SHA256="$checkpoint_sha" \
STAGE26V_GEOMETRY_OUTPUT="$out" \
/usr/bin/yade -n -x "$script" > "$supervisor/stdout.log" 2> "$supervisor/stderr.log"
code=$?
printf '%s\n' "$code" > "$supervisor/runner_exit_code.txt"
cat "$supervisor/stdout.log"
cat "$supervisor/stderr.log" >&2
echo "CODEX_STAGE26V_GEOMETRY_EXIT=$code"
exit "$code"
