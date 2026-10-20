"""Read-only corrected-field loader checks and matched initial-centre probe.

Reuses the frozen seed2 centres and the predeclared two-CPD2-cell near-grain
split. No trajectory, particle force, or material parameter is changed.
"""
from __future__ import annotations

import argparse
import io
import sys
import unittest
from pathlib import Path

import numpy as np

import requalify_stationary_flows_v1 as run
import load_stationary_field_v1 as loader
import test_stationary_requalification_v1 as tests
import test_steady_flow_gate_v1 as old_tests


def stats(rows):
    v = np.array([r["velocity_difference_over_u0"] for r in rows])
    g = np.array([r["gradient_difference_over_u0_per_dx2"] for r in rows])
    return {"count":len(rows), "velocity_median":float(np.median(v)), "velocity_p90":float(np.quantile(v,.9)),
            "velocity_maximum":float(v.max()), "gradient_median":float(np.median(g)), "gradient_p90":float(np.quantile(g,.9))}


def main(output):
    run.require(output.is_relative_to(run.ROOT / "stage114_evaluations") and not output.exists(), "fresh output required")
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(m) for m in [tests,old_tests]])
    log = io.StringIO()
    tested = unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    run.require(tested.wasSuccessful(),log.getvalue())
    protocol_path = run.ROOT / "stage109_designs/shape_flow_protocol_20260914/protocol.json"
    starts_path = run.ROOT / "stage95_designs/common_admissible_population_01/starts_s2.json"
    protocol = run.audit.read(protocol_path)
    run.require(run.audit.sha(protocol_path) == run.audit.read(protocol_path.with_name("completion.json"))["protocol_sha256"],"protocol drift")
    run.require(run.audit.sha(starts_path) == protocol["input_hashes"][str(starts_path)],"start drift")
    design = run.audit.read(run.DESIGN)
    original = run.audit.read(design["lineage"]["stage27_config"]["path"])
    dependency_bindings = {k:original["lineage"][k] for k in ["stage13_runner","stage17_adapter","stage13_execution_manifest","stage13_qualification","cuda_source"]}
    run.verify_bindings(dependency_bindings)
    qualification = run.audit.read(dependency_bindings["stage13_execution_manifest"]["path"])
    cpu_reference = run.bind(run.audit.legacy.stage13.arbitrary.__file__)
    run.require(cpu_reference["sha256"] == qualification["runtime_hashes"]["arbitrary_solid_reference_sha256"],"independent CPU reference changed")
    dependency_bindings["arbitrary_solid_reference"] = cpu_reference
    combinations = [(2,.5,2),(2,1.,2),(2,2.,2),(1,1.,2),(3,1.,2),(2,1.,4)]
    loaded = []
    fields = {}
    for seed,factor,cpd in combinations:
        field,geometry,metadata = loader.load(seed,factor,cpd)
        run.require(abs(metadata["pv_per_second"]*metadata["two_pore_volume_horizon_s"]-2) < 1e-14,"PV horizon inconsistency")
        loaded.append(metadata)
        if seed == 2 and factor == 1:
            fields[cpd]=(field,geometry)
        print("LOADED",metadata["case_id"],metadata["achieved_mean_interstitial_velocity_m_s"],flush=True)
    unsupported = []
    for seed,factor,cpd in [(1,.5,2),(1,2.,2),(3,.5,2),(3,2.,2),(2,.5,4),(2,2.,4)]:
        try:
            loader.load(seed,factor,cpd)
        except RuntimeError:
            unsupported.append([seed,factor,cpd])
        else:
            raise RuntimeError("unsolved flow silently accepted")
    f2,g2 = fields[2]
    f4,g4 = fields[4]
    run.require(np.array_equal(g2["sand_centres_m"],g4["sand_centres_m"]) and np.array_equal(g2["sand_radii_m"],g4["sand_radii_m"]),"grains differ")
    centres,radii = g2["sand_centres_m"],g2["sand_radii_m"]
    length = float(g2["cell_length_m"][0])
    starts = run.audit.read(starts_path)
    run.require([s["id"] for s in starts] == list(range(256)),"start set/order drift")
    rows=[]
    for s in starts:
        position=np.array(s["position_m"])
        diff=np.abs(centres-position)
        diff=np.minimum(diff,length-diff)
        clearance=float(np.min(np.linalg.norm(diff,axis=1)-radii))
        v2,d2=f2.sample(position)
        v4,d4=f4.sample(position)
        rows.append({"sample_id":s["id"],"centre_clearance_m":clearance,
                     "velocity_difference_over_u0":float(np.linalg.norm(v2-v4)/1e-4),
                     "gradient_difference_over_u0_per_dx2":float(np.linalg.norm(d2-d4)*f2.dx/1e-4)})
    near=[r for r in rows if r["centre_clearance_m"] <= 2*f2.dx]
    far=[r for r in rows if r["centre_clearance_m"] > 2*f2.dx]
    result={"status":"corrected_field_load_and_centre_probe_complete_no_transport", "passed":True,
            "unit_tests":{"count":tested.testsRun,"passed":True,"log":log.getvalue(),
                          "sources":[run.bind(tests.__file__),run.bind(old_tests.__file__)]},
            "loaded_fields":loaded,"unsupported_combinations_rejected":unsupported,
            "probe":{"all":stats(rows),"near_grain":stats(near),"farther":stats(far),"clearance_split_m":2*f2.dx,"rows":rows},
            "probe_definition":"Velocity and gradient differences use direct SI scaling of each stationary solution, NOT separate mean normalization. U0 is the nominal reference, 1e-4 m/s. No particle motion was integrated.",
            "qualified_solver_dependencies":dependency_bindings,
            "bindings":{"protocol":run.bind(protocol_path),"starts":run.bind(starts_path),"script":run.bind(__file__)},
            "authority":{"particle_transport":False,"campaign":False},
            "next":"Freeze an adapter/checkpoint contract using corrected fields and achieved-flow PV horizons before matched both-shape dynamic sentinels."}
    output.mkdir(parents=True)
    run.write(output / "results.json",result)
    run.write(output / "completion.json",{"status":result["status"],"passed":True,"results_sha256":run.audit.sha(output/"results.json")})
    print({k:v for k,v in result["probe"].items() if k != "rows"})


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    main(p.parse_args().output.resolve())
