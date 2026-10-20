"""Run bounded planar CPU flow benchmarks and manufactured cell-change tests."""
import argparse
import io
import json
import platform
import time
import unittest
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from moving_wall_reference_v1 import moving_reflection,equilibrium,couette,mask_change_audit,require_conservative
from verify_stage36e_link_extraction_v1 import AccountingTests,GeometryTests,WrenchTests,LinkTests
from verify_stage36d_wrench_transfer_v1 import check_parent,sha,ROOT

STAGING=ROOT/'stage36_staging'
PARENT=ROOT/'stage36_evaluations/stage36e_link_extraction_20260906/verification_01/verification.json'


def changed(density=1.):
    old=np.zeros((19,3));new=np.zeros((19,3))
    old[:,0:2]=equilibrium(np.ones(2),np.array([[.01,0],[0,0],[0,0]]))
    new[:,1]=old[:,1]
    new[:,2]=equilibrium(np.array([density]),np.array([[0],[.02],[0]]))[:,0]
    return old,new,np.array([True,True,False]),np.array([False,True,True]),np.array([[1.,0,0],[0,0,0],[0,1,0]])


class MovingTests(unittest.TestCase):
    def test_01_stationary_exact_reflection(self):
        f=np.array([.03,.04]);incoming,j=moving_reflection(f,np.array([7,9]),[0,0,0])
        np.testing.assert_array_equal(incoming,f)
        np.testing.assert_array_equal(j,[[-.06,-.06,0],[-.08,.08,0]])

    def test_02_known_wall_correction(self):
        incoming,j=moving_reflection(np.array([.03]),np.array([7]),[.01,0,0])
        self.assertAlmostEqual(incoming[0],.03+.01/6)
        np.testing.assert_allclose(j,[[-(.06+.01/6),-(.06+.01/6),0]],rtol=0,atol=1e-15)

    def test_03_invalid_reflection(self):
        for vel in [[np.nan,0,0],[.1,0,0]]:
            with self.assertRaises(ValueError):moving_reflection(np.array([.03]),np.array([7]),vel)
        with self.assertRaises(ValueError):moving_reflection(np.array([-.01]),np.array([7]),[0,0,0])

    def test_04_equal_volume_change(self):
        args=changed();a=mask_change_audit(*args,[0,0,0]);require_conservative(a)
        np.testing.assert_allclose(a['required_body_impulse_lu'],[.01,-.02,0],atol=1e-15)
        np.testing.assert_allclose(a['momentum_bookkeeping_residual'],0,atol=1e-15)

    def test_05_refill_mass_defect_rejected(self):
        a=mask_change_audit(*changed(1.1),[0,0,0])
        self.assertAlmostEqual(a['uncompensated_mass_change_lu'],.1)
        with self.assertRaises(ValueError):require_conservative(a)

    def test_06_angular_origin_shift(self):
        args=changed();a=mask_change_audit(*args,[0,0,0]);b=mask_change_audit(*args,[1,2,3])
        expected=np.array(a['required_body_angular_impulse_lu'])-np.cross([1,2,3],a['required_body_impulse_lu'])
        np.testing.assert_allclose(b['required_body_angular_impulse_lu'],expected,atol=1e-15)

    def test_07_no_silent_retained_modification(self):
        old,new,a,b,x=changed();new[:,1]*=1.01
        with self.assertRaises(ValueError):mask_change_audit(old,new,a,b,x,[0,0,0])

    def test_08_solid_state_contamination(self):
        old,new,a,b,x=changed();new[0,0]=.1
        with self.assertRaises(ValueError):mask_change_audit(old,new,a,b,x,[0,0,0])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    parents=check_parent(PARENT)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests))
    stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    deadline=time.monotonic()+120
    runs=[]
    for n in (8,16,32):
        row=couette(n,.08/n,deadline=deadline);row['case_id']=f'refinement_N{n}';runs.append(row)
        print('COMPLETED '+row['case_id'],flush=True)
    for name,top,bottom,initial in [('zero',0,0,0),('reverse',-.01,0,0),('half',.005,0,0),('comoving',.01,.01,.01)]:
        row=couette(8,top,bottom,initial,deadline=deadline);row['case_id']=name;runs.append(row)
        print('COMPLETED '+name,flush=True)
    gates={
        'all_mass_drift_le_1e_10':all(r['max_mass_relative_drift']<=1e-10 for r in runs),
        'all_step_momentum_residual_le_1e_11':all(r['max_step_momentum_residual_lu']<=1e-11 for r in runs),
        'all_final_profile_error_le_1e_6':all(r['final_profile_normalized_max_error']<=1e-6 for r in runs),
        'all_wall_shear_error_le_1e_5':all(r['wall_shear_relative_error']<=1e-5 for r in runs),
        'fine_transient_rms_le_0p003':runs[2]['transient_normalized_rms_error']<=.003,
        'transient_error_reduces':runs[2]['transient_normalized_rms_error']<.7*runs[1]['transient_normalized_rms_error']}
    cell={'equal_density_transition':mask_change_audit(*changed(),[0,0,0]),
          'unequal_refill_negative_control':mask_change_audit(*changed(1.1),[0,0,0])}
    (output/'flow_results.json').write_text(json.dumps({'runs':runs,'gates':gates},indent=2),encoding='utf-8')
    (output/'cell_change_audit.json').write_text(json.dumps(cell,indent=2),encoding='utf-8')
    sources=[Path(__file__).resolve(),STAGING/'moving_wall_reference_v1.py',STAGING/'STAGE36F_MOVING_WALL_CONTRACT.md',PARENT]
    report={'passed':tests.wasSuccessful() and all(gates.values()),'unit_tests_run':tests.testsRun,'new_unit_tests':8,
            'regression_tests':73,'failures':len(tests.failures),'errors':len(tests.errors),'cpu_planar_flow_runs':len(runs),
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'numpy':np.__version__,
            'source_hashes':{str(p):sha(p) for p in sources},'artifact_hashes':{str(p):sha(p) for p in output.iterdir()},
            'parent_binding_checks':parents,'gates':gates,'production_cuda_modified':False,'gpu_jobs_started':0,
            'moving_mask_refill_qualified':False,'curved_body_motion_verified':False,'soil_release_prediction':False}
    (output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'tests':tests.testsRun,'gates':gates,'metrics':[{k:r[k] for k in ['case_id','max_mass_relative_drift','max_step_momentum_residual_lu','final_profile_normalized_max_error','wall_shear_relative_error']} for r in runs]},indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
