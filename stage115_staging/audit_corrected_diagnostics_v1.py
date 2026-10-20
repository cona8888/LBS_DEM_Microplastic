"""Freeze test evidence before any Stage115 particle execution."""
import io
import unittest
from pathlib import Path

import corrected_transport_v1 as api
import test_corrected_transport_v1 as tests


def main():
    design=api.read(api.DESIGN)
    api.verify_design(design)
    log=io.StringIO()
    tested=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    api.require(tested.wasSuccessful(),log.getvalue())
    checks={"all_unit_tests":tested.wasSuccessful(),"thirty_six_cases":len(design["cases"])==36,
            "three_time_refinements":sorted({c["refinement"] for c in design["cases"]})==[.25,.5,1.],
            "same_short_horizon":{c["horizon_s"] for c in design["cases"]}=={.25},
            "original_sentinel_ids":all(c["sample_id"]=={1:77,2:0,3:154}[c["seed"]] for c in design["cases"]),
            "no_population_authority":design["authority"]["population_campaign"] is False}
    result={"passed":all(checks.values()),"checks":checks,"unit_tests":tested.testsRun,"test_log":log.getvalue(),
            "design_sha256":api.sha(api.DESIGN),"auditor_sha256":api.sha(__file__),"test_source_sha256":api.sha(tests.__file__)}
    api.write(api.DESIGN.parent/"pre_execution_audit.json",result)
    print(result)


if __name__=="__main__":main()
