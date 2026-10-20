#!/usr/bin/env bash
set -euo pipefail
export STAGE29D_UNIT_OUTPUT=/mnt/c/MATDEM_MICROPLASTIC/stage29_tests/stage29d_yade_four_fibre_groupmask_20260826/unit_01
exec /usr/bin/yade -n -x /mnt/c/MATDEM_MICROPLASTIC/stage29_staging/test_stage29d_yade_four_fibre_groupmask_v1.py
