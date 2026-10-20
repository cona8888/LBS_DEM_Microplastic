"""Run manufactured accounting fixtures, never a DEM/LBM simulation."""
import argparse
import copy
import hashlib
import io
import json
import math
import platform
import random
import unittest
from datetime import datetime, timezone
from pathlib import Path

from release_accounting_v1 import Body, Ledger, fraction_left, partition

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
PARENT = ROOT / "stage36_designs/stage36a_release_transport_feasibility_20260906/release_01/planning_audit.json"


def standard():
    return Body("f1", 1e-9, 0.2, 0.05)


def ledger():
    return Ledger([standard()], [("f1", 0.5)], 0.0, 1.0, 2e-6)


def quadrature_fraction(body, plane, n):
    # Independent physical-area midpoint integral, split at cylinder/cap joins.
    r, half = body.radius_m, body.length_m / 2
    edges = [-half-r, -half, half, half+r]
    volume = 0.0
    for lo, top in zip(edges[:-1], edges[1:]):
        hi = min(top, plane)
        if hi <= lo:
            continue
        dx = (hi-lo)/n
        areas = []
        for i in range(n):
            x = lo + (i+0.5)*dx
            excess = max(0.0, abs(x)-half)
            areas.append(math.pi * max(0.0, r*r-excess*excess))
        volume += math.fsum(areas)*dx
    return volume/(math.pi*r*r*body.length_m + 4*math.pi*r**3/3)


def quadrature_errors():
    body = standard()
    planes = [-0.139, -0.107, -0.031, 0.021, 0.121, 0.143]
    return [{"cells_per_axial_piece": n, "maximum_fraction_error": max(
        abs(quadrature_fraction(body, p, n)-fraction_left(body, p)) for p in planes
    )} for n in (32, 128, 512)]


class AccountingTests(unittest.TestCase):
    def close(self, a, b, scale=1.0):
        self.assertLessEqual(abs(a-b), 1e-12*scale)

    def test_01_half_and_extrema(self):
        b = standard()
        for x, want in [(-0.2, 0), (0, 0.5), (0.2, 1)]:
            self.close(fraction_left(b,x), want)

    def test_02_hemisphere_fraction(self):
        self.close(fraction_left(standard(), -0.1), 0.125)

    def test_03_sphere_limit(self):
        b = Body("sphere", 1, 0, 1)
        self.close(fraction_left(b, 0), 0.5)
        self.close(fraction_left(b, -0.5), 5/32)

    def test_04_symmetry(self):
        for x in [-0.149, -0.12, -0.01, 0.01, 0.1, 0.149]:
            self.close(fraction_left(standard(),x)+fraction_left(standard(),-x), 1)

    def test_05_quadrature_refinement(self):
        e = [r["maximum_fraction_error"] for r in quadrature_errors()]
        self.assertGreater(e[0],e[1])
        self.assertGreater(e[1],e[2])
        self.assertLessEqual(e[2],1e-5)

    def test_06_no_motion(self):
        row=ledger().step(1,[("f1",0.5)])
        self.close(row["inside_mass_kg"],1e-9,1e-9)
        self.assertEqual(row["net_downstream_fraction"],0)
        self.assertEqual(row["complete_exit_events"],0)

    def test_07_partial_cap_not_whole_body(self):
        row=ledger().step(1,[("f1",0.86)])
        r,h,L=0.05,0.01,0.2
        want=math.pi*h*h*(r-h/3)/(math.pi*r*r*L+4*math.pi*r**3/3)
        self.close(row["net_downstream_fraction"],want)
        self.assertEqual(row["complete_exit_events"],0)

    def test_08_centre_crossing_is_half(self):
        row=ledger().step(1,[("f1",1)])
        self.close(row["net_downstream_fraction"],0.5)
        self.assertEqual(row["complete_exit_events"],0)

    def test_09_complete_exit(self):
        row=ledger().step(1,[("f1",1.2)])
        self.close(row["net_downstream_fraction"],1)
        self.assertEqual(row["complete_exit_ids_this_step"],["f1"])

    def test_10_reversal_and_unique_counts(self):
        log=ledger()
        log.step(1,[("f1",1.2)])
        row=log.step(2,[("f1",0.5)])
        self.close(row["net_downstream_fraction"],0)
        self.close(row["gross_outward_mass_kg"],1e-9,1e-9)
        self.close(row["gross_return_mass_kg"],1e-9,1e-9)
        row=log.step(3,[("f1",1.2)])
        self.close(row["gross_outward_mass_kg"],2e-9,1e-9)
        self.close(row["net_downstream_fraction"],1)
        self.assertEqual(row["complete_exit_events"],2)
        self.assertEqual(row["unique_ever_completely_exited"],1)

    def test_11_upstream_escape(self):
        row=ledger().step(1,[("f1",-0.2)])
        self.close(row["upstream_mass_kg"],1e-9,1e-9)
        self.close(row["gross_upstream_mass_kg"],1e-9,1e-9)
        self.assertEqual(row["net_downstream_fraction"],0)

    def test_12_opposite_flows_not_cancelled(self):
        bodies=[Body("a",1,0.2,0.05),Body("b",1,0.2,0.05)]
        log=Ledger(bodies,[("a",0.5),("b",0.5)],0,1,1)
        log.step(1,[("a",1.2),("b",0.5)])
        row=log.step(2,[("a",0.5),("b",1.2)])
        self.close(row["outward_mass_this_step_kg"],1)
        self.close(row["return_mass_this_step_kg"],1)
        self.close(row["net_downstream_fraction"],0.5)

    def test_13_variable_steps_and_water(self):
        log=ledger()
        log.step(0.1,[("f1",0.6)],inlet_water_m3=2e-6,outlet_water_m3=1e-6)
        row=log.step(2.7,[("f1",1)],inlet_water_m3=4e-6,outlet_water_m3=2e-6)
        self.close(row["pore_volumes_flushed"],3)
        self.close(row["diagnostic_outward_mass_per_collected_water_kg_m3"],0.00025)
        self.assertEqual(row["event_time_bracket_s"],[0.1,2.7])

    def test_14_zero_collected_water_is_undefined(self):
        row=ledger().step(1,[("f1",1.2)])
        self.assertIsNone(row["diagnostic_outward_mass_per_collected_water_kg_m3"])

    def test_15_initial_id_guards(self):
        for bodies,poses in [([standard(),standard()],[("f1",0.5)]),
                             ([standard()],[]),([],[])]:
            with self.assertRaises(ValueError):
                Ledger(bodies,poses,0,1,1)

    def test_16_invalid_update_is_atomic(self):
        invalid = [[], [("unknown",0.5)], [("f1",0.5),("f1",0.6)],[("f1",float("nan"))]]
        for poses in invalid:
            log=ledger()
            before=copy.deepcopy(log.__dict__)
            with self.assertRaises(ValueError):
                log.step(1,poses,inlet_water_m3=1)
            self.assertEqual(log.__dict__,before)

    def test_17_invalid_time_and_water(self):
        for t,wi,wo in [(0,0,0),(-1,0,0),(float("inf"),0,0),(1,-1,0),(1,0,-1),(1,0,float("nan"))]:
            log=ledger()
            before=copy.deepcopy(log.__dict__)
            with self.assertRaises(ValueError):
                log.step(t,[("f1",0.5)],wi,wo)
            self.assertEqual(log.__dict__,before)

    def test_18_invalid_shapes_and_domain(self):
        for mass,L,r in [(0,1,1),(1,-1,1),(1,1,0),(float("nan"),1,1),(1,1,float("inf"))]:
            with self.assertRaises(ValueError):
                Body("b",mass,L,r)
        for a,b,v in [(1,0,1),(0,1,0),(0,float("nan"),1)]:
            with self.assertRaises(ValueError):
                Ledger([standard()],[("f1",0.5)],a,b,v)

    def test_19_initial_partial_outside_rejected(self):
        with self.assertRaises(ValueError):
            Ledger([standard()],[("f1",0.01)],0,1,1)

    def test_20_scale_invariance(self):
        for scale in (1e-6,1,1e6):
            b=Body("f",1e-18,0.2*scale,0.05*scale)
            parts=partition(b,0.9*scale,0,scale)
            self.close(parts[2],0.125)

    def test_21_monotone_sampling_refinement(self):
        for n in (8,32,128):
            log=ledger()
            for i in range(1,n+1):
                row=log.step(i/n,[("f1",0.5+0.75*i/n)])
            self.close(row["net_downstream_fraction"],1)
            self.close(row["gross_outward_mass_kg"],1e-9,1e-9)
            self.close(row["gross_return_mass_kg"],0,1e-9)
            self.assertEqual(row["complete_exit_events"],1)

    def test_22_many_prescribed_reversals(self):
        rng=random.Random(3602)
        log=ledger()
        for i in range(1,1001):
            row=log.step(i,[("f1",rng.uniform(-0.3,1.3))])
            self.assertLessEqual(row["maximum_relative_balance_residual"],1e-12)
            self.assertGreaterEqual(row["net_downstream_fraction"],0)
            self.assertLessEqual(row["net_downstream_fraction"],1)

    def test_23_body_spans_both_planes(self):
        p=partition(Body("long",1,4,0.5),0.5,0,1)
        self.assertGreater(p[0],0)
        self.assertGreater(p[2],0)
        self.close(math.fsum(p),1)
        self.close(p[0],p[2])

    def test_24_mass_weighting_not_count_weighting(self):
        log=Ledger([Body("a",1,0.2,0.05),Body("b",3,0.2,0.05)],[("a",0.5),("b",0.5)],0,1,1)
        row=log.step(1,[("a",1.2),("b",0.5)])
        self.close(row["net_downstream_fraction"],0.25)

    def test_25_boundary_tangency(self):
        b=Body("f",1,0.125,0.0625)
        log=Ledger([b],[("f",0.5)],0,1,1)
        row=log.step(1,[("f",0.875)])
        self.assertEqual(row["net_downstream_fraction"],0)
        row=log.step(2,[("f",1.125)])
        self.assertEqual(row["net_downstream_fraction"],1)
        self.assertEqual(row["complete_exit_events"],1)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    allowed=ROOT/"stage36_evaluations/stage36b_release_accounting_20260906"
    if not output.is_relative_to(allowed) or output == allowed:
        raise ValueError("output must be a new attempt below the Stage36B evaluation directory")
    if output.exists():
        raise FileExistsError("immutable output already exists")
    parent=json.loads(PARENT.read_text(encoding="utf-8"))
    for relative,expected in parent["sha256_bindings"].items():
        if sha(ROOT/relative) != expected:
            raise ValueError("parent lineage hash mismatch: "+relative)
    output.mkdir(parents=True)
    buffer=io.StringIO()
    result=unittest.TextTestRunner(stream=buffer,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AccountingTests))
    (output/"tests.txt").write_text(buffer.getvalue(),encoding="utf-8")
    log=ledger()
    demo=[]
    for t,x in enumerate([0.5,0.86,1.0,1.2,1.0,0.5,1.2],start=1):
        row=log.step(t,[("f1",x)],inlet_water_m3=2e-6,outlet_water_m3=2e-6)
        row["prescribed_centre_m"]=x
        demo.append(row)
    (output/"manufactured_history.json").write_text(json.dumps(demo,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    passed=result.wasSuccessful() and result.testsRun == 25
    sources=[Path(__file__).resolve(),ROOT/"stage36_staging/release_accounting_v1.py",
             ROOT/"stage36_staging/STAGE36B_RELEASE_ACCOUNTING_CONTRACT.md",PARENT]
    artifacts=[output/"tests.txt",output/"manufactured_history.json"]
    report={"status":"passed_axial_capsule_accounting_tests" if passed else "failed_accounting_tests",
            "passed":passed,"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
            "timestamp_utc":datetime.now(timezone.utc).isoformat(),"python":platform.python_version(),
            "quadrature_errors":quadrature_errors(),"scope":"manufactured axial-capsule bookkeeping only",
            "maximum_demo_relative_balance_residual":max(r["maximum_relative_balance_residual"] for r in demo),
            "transport_physics_verified":False,"general_curved_fibre_clipping_verified":False,
            "soil_pilot_execution_authorized":False,"physics_simulations_started":0,
            "source_hashes":{str(p):sha(p) for p in sources},"artifact_hashes":{str(p):sha(p) for p in artifacts}}
    (output/"verification.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(buffer.getvalue())
    print(json.dumps(report,indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
