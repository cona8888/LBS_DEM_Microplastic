"""Serialization-only V2: preserve exact polynomial V1 and its failed output."""
from pathlib import Path
import sys
import isolate_mixed_mode_polynomials_v1 as old


def run():
    failed=old.OUT/'failure.json'
    r=old.api.read(failed)
    assert r['new_trajectory_steps']==0 and 'integer string conversion' in r['error'] and r['modes_completed']==0
    inputs={str(p):old.api.sha(p) for p in (Path(__file__),Path(old.__file__),failed)}
    # Exact Sturm coefficients are large integers. Bound serialization without
    # changing any mathematical operation or bypassing a scientific gate.
    sys.set_int_max_str_digits(100000)
    old.OUT=old.ROOT/'stage210_evaluations/three_contact_failure_20261001/mixed_mode_polynomials_02'
    old.run()
    old.api.verify_mapping(inputs)
    old.job.commit(old.OUT/'serialization_bridge.json',dict(inputs=inputs,original_algorithm_unchanged=True,
        new_trajectory_steps=0,integer_decimal_serialization_digit_limit=100000,
        preserved_v1_failure=True,results_sha256=old.api.sha(old.OUT/'results.json')))


if __name__=='__main__':run()
