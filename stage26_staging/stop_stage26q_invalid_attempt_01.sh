#!/usr/bin/env bash
set -euo pipefail

pattern='/usr/bin/yade -n -x /mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26q_clean_density_controller_v1.py'
mapfile -t pids < <(pgrep -f "$pattern" || true)
if [[ ${#pids[@]} -ne 1 ]]; then
    printf 'STAGE26Q_STOP_REFUSAL=expected_one_exact_process found=%s pids=%s\n' "${#pids[@]}" "${pids[*]-}" >&2
    exit 75
fi
pid=${pids[0]}
cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline")
if [[ "$cmd" != *"$pattern"* ]]; then
    printf 'STAGE26Q_STOP_REFUSAL=cmdline_mismatch pid=%s cmd=%s\n' "$pid" "$cmd" >&2
    exit 76
fi
kill -INT "$pid"
for _ in $(seq 1 50); do
    if ! kill -0 "$pid" 2>/dev/null; then
        printf 'STAGE26Q_INVALID_PROCESS_STOPPED=%s\n' "$pid"
        exit 0
    fi
    sleep 0.1
done
printf 'STAGE26Q_STOP_REFUSAL=interrupt_not_acknowledged pid=%s\n' "$pid" >&2
exit 77
