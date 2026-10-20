#!/usr/bin/env bash
set -euo pipefail
export STAGE28A_UNIT_OUTPUT=/mnt/c/MATDEM_MICROPLASTIC/stage28_tests/stage28a_yade_groupmask_self_filter_20260824/unit_03
exec /usr/bin/yade -n -x /mnt/c/MATDEM_MICROPLASTIC/stage28_staging/test_stage28a_yade_groupmask_self_filter_v4.py
