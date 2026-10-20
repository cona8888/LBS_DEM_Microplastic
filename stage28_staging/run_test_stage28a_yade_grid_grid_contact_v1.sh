#!/usr/bin/env bash
set -euo pipefail
export STAGE28A_UNIT_OUTPUT=/mnt/c/MATDEM_MICROPLASTIC/stage28_tests/stage28a_yade_grid_grid_contact_20260824/unit_01
exec /usr/bin/yade -n -x /mnt/c/MATDEM_MICROPLASTIC/stage28_staging/test_stage28a_yade_grid_grid_contact_v1.py
