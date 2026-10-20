"""CPU-only immutable refill screening; records rejected candidates explicitly."""
import argparse
import io
import json
import platform
import time
import unittest
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from refill_screen_v1 import ae6,pool6,moments,coordinates,angular,ledger_check
from moving_wall_reference_v1 import equilibrium
from verify_stage36f_moving_wall_v1 import AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests
from verify_stage36d_wrench_transfer_v1 import ROOT,sha,check_parent

STAGING=ROOT/'stage36_staging'
PARENT=ROOT/'stage36_evaluations/stage36f_moving_wall_20260906/verification_01/verification.json'


def fixture(n=16,shift=1.,gradient=False):
    x=coordinates((n,n,n));centre=np.array([n/2+.13,n/2+.17,n/2+.19]);radius=n/5
    a=(np.linalg.norm(x-centre,axis=1)>radius).reshape((n,n,n))
    b=(np.linalg.norm(x-centre-[shift,0,0],axis=1)>radius).reshape(a.shape)
    rho=1+.001*x[:,0] if gradient else np.ones(len(x))
    f=equilibrium(rho,np.tile([[.01],[0],[0]],(1,len(x)))).reshape((19,)+a.shape)
    exact=f.copy();f[:,~a]=0;exact[:,~b]=0
    return f,a,b,exact


class RefillTests(unittest.TestCase):
    def test_01_no_change_exact(self):
        f,a,_,_=fixture()
        np.testing.assert_array_equal(ae6(f,a,a)[0],f)
        np.testing.assert_array_equal(pool6(f,a,a)[0],f)

    def test_02_population_conservation(self):
        f,a,b,_=fixture();g,_,_=pool6(f,a,b)
        np.testing.assert_allclose(g.sum(axis=(1,2,3)),f.sum(axis=(1,2,3)),rtol=1e-13)

    def test_03_positive_solid_zero(self):
        f,a,b,_=fixture();g,_,_=pool6(f,a,b)
        self.assertTrue(np.all(g[:,b]>0));self.assertTrue(np.all(g[:,~b]==0))

    def test_04_local_edges(self):
        f,a,b,_=fixture();g,e,w=pool6(f,a,b);x=coordinates(a.shape)
        np.testing.assert_array_equal(np.linalg.norm(x[e[:,1]]-x[e[:,0]],axis=1),1)
        self.assertTrue(np.all((a|b).ravel()[e]))
        self.assertTrue(np.all((a&b).ravel()[e].any(axis=1)))

    def test_05_input_not_modified(self):
        f,a,b,_=fixture();copy=f.copy();ae6(f,a,b);pool6(f,a,b)
        np.testing.assert_array_equal(f,copy)

    def test_06_ae_uniform_exact(self):
        f,a,b,exact=fixture();g,_=ae6(f,a,b)
        np.testing.assert_allclose(g,exact,rtol=0,atol=1e-16)

    def test_07_ae_affine_exact(self):
        f,a,b,exact=fixture(gradient=True);g,_=ae6(f,a,b)
        np.testing.assert_allclose(g,exact,rtol=0,atol=3e-16)

    def test_08_invalid_masks(self):
        f,a,b,_=fixture()
        for fn in (ae6,pool6):
            with self.assertRaises(ValueError):fn(f,a.astype(int),b)
            with self.assertRaises(ValueError):fn(f,a,b[:2])

    def test_09_invalid_populations(self):
        f,a,b,_=fixture();f[0][a]=np.nan
        for fn in (ae6,pool6):
            with self.assertRaises(ValueError):fn(f,a,b)

    def test_10_no_unsupported_isolated_refill(self):
        a=np.zeros((5,5,5),bool);b=a.copy();b[2,2,2]=True;f=np.zeros((19,5,5,5))
        for fn in (ae6,pool6):
            with self.assertRaises(ValueError):fn(f,a,b)

    def test_11_scalar_ledger_reconstruction(self):
        f,a,b,_=fixture();g,e,w=pool6(f,a,b);r=ledger_check(f,g,e,w)
        self.assertLessEqual(r['reconstruction_max_error'],1e-13)
        self.assertLessEqual(max(abs(v) for v in r['ledger_angular_residual_lu']),1e-10)

    def test_12_angular_origin_transform(self):
        f,a,b,_=fixture();g,_,_=pool6(f,a,b);o=np.array([2,3,4])
        dp=(moments(g)[1]-moments(f)[1]).sum(axis=1)
        np.testing.assert_allclose(angular(g,o)-angular(f,o),angular(g)-angular(f)-np.cross(o,dp),atol=1e-10)

    def test_13_unphysical_extrapolation_rejected(self):
        a=np.zeros((5,5,5),bool);a[2,2,3:]=True;b=a.copy();b[2,2,2]=True
        f=np.zeros((19,5,5,5));f[:,2,2,3]=.01;f[:,2,2,4]=.1
        with self.assertRaises(ValueError):ae6(f,a,b)

    def test_14_uniform_mass_count_identity(self):
        f,a,b,_=fixture(shift=.5);g,_=ae6(f,a,b)
        self.assertAlmostEqual(float(g.sum()-f.sum()),int(b.sum())-int(a.sum()),places=10)


def metrics(f,g,a,b,method,ledger=None):
    rho,p=moments(g);u=p[:,b.ravel()]/rho[b.ravel()]
    m0=float(f.sum());dm=float(g.sum()-m0)
    ret=a&b;changed=~(a==b);near=changed.copy()
    # Independent geometric definition of the allowed one-cell affected shell.
    for point in np.argwhere(changed):
        for axis in range(3):
            for s in (-1,1):
                q=point.copy();q[axis]+=s
                if np.all(q>=0) and np.all(q<a.shape):near[tuple(q)]=True
    far=ret&~near
    row={'mass_change_lu':dm,'mass_relative_change':abs(dm)/m0,
         'fluid_count_change':int(b.sum())-int(a.sum()),
         'covered_cells':int((a&~b).sum()),'exposed_cells':int((b&~a).sum()),
         'density_min':float(rho[b.ravel()].min()),'density_max':float(rho[b.ravel()].max()),
         'density_max_error':float(np.max(np.abs(rho[b.ravel()]-1))),
         'velocity_max_error_lu':float(np.max(np.abs(u-np.array([[.01],[0],[0]])))),
         'momentum_change_lu':(moments(g)[1].sum(axis=1)-moments(f)[1].sum(axis=1)).tolist(),
         'orbital_angular_change_lu':(angular(g)-angular(f)).tolist(),
         'far_field_exact':bool(np.array_equal(f[:,far],g[:,far])),
         'population_total_relative_error':float(np.max(np.abs(g.sum(axis=(1,2,3))/f.sum(axis=(1,2,3))-1)))}
    gates={'positive_finite':bool(np.isfinite(g).all() and np.all(g[:,b]>0)),
           'solid_zero':bool(np.all(g[:,~b]==0)), 'mass_le_1e_12':row['mass_relative_change']<=1e-12,
           'density_error_le_0p01':row['density_max_error']<=.01,
           'velocity_error_le_1e_10':row['velocity_max_error_lu']<=1e-10,
           'far_field_exact':row['far_field_exact']}
    if method=='POOL6':
        row['ledger']=ledger
        gates.update(population_conservation=row['population_total_relative_error']<=1e-12,
                     ledger_reconstruction=ledger['reconstruction_max_error']<=1e-13,
                     edge_locality=ledger['max_edge_length_lu']<=1)
    row['gates']=gates;row['candidate_screen_passed']=all(gates.values())
    return row


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    bindings=check_parent(PARENT)
    classes=(AccountingTests,GeometryTests,WrenchTests,LinkTests,MovingTests,RefillTests)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes)
    log=io.StringIO();tests=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    (out/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():
        (out/'failure.json').write_text(json.dumps({'reason':'unit tests failed','tests':tests.testsRun}),encoding='utf-8')
        print(log.getvalue());raise SystemExit(1)
    start=time.monotonic();rows=[]
    for n in (16,24,32):
        for shift in (0.,.25,.5,1.):
            for method in ('AE6','POOL6'):
                if time.monotonic()-start>120:raise TimeoutError('CPU screening cap')
                f,a,b,exact=fixture(n,shift);name=f'{method}_N{n}_shift{shift:g}'
                extra={};ledger=None
                if method=='AE6':g,rays=ae6(f,a,b);extra['rays']=rays
                else:
                    g,e,w=pool6(f,a,b);extra.update(edges=e,transferred_populations=w)
                    ledger=ledger_check(f,g,e,w)
                np.savez_compressed(out/(name+'.npz'),old=f,new=g,old_fluid=a,new_fluid=b,exact_uniform=exact,**extra)
                row=metrics(f,g,a,b,method,ledger);row.update(case_id=name,n=n,shift_lu=shift,method=method)
                rows.append(row);print(name+' screen_passed='+str(row['candidate_screen_passed']),flush=True)
    (out/'screen_results.json').write_text(json.dumps({'cases':rows},indent=2),encoding='utf-8')
    summary={m:{'trials':sum(r['method']==m for r in rows),
                'trials_passing_all_screen_gates':sum(r['method']==m and r['candidate_screen_passed'] for r in rows),
                'max_mass_relative_change':max(r['mass_relative_change'] for r in rows if r['method']==m),
                'max_density_error':max(r['density_max_error'] for r in rows if r['method']==m)} for m in ('AE6','POOL6')}
    sources=[Path(__file__).resolve(),STAGING/'refill_screen_v1.py',STAGING/'STAGE36G_REFILL_SCREEN_CONTRACT.md',PARENT]
    report={'execution_completed':True,'unit_tests_passed':tests.wasSuccessful(),'unit_tests_run':tests.testsRun,
            'new_unit_tests':14,'regression_tests':81,'cpu_mask_transition_trials':len(rows),
            'full_flow_steps_run':0,'refill_qualified_for_moving_body':False,'soil_release_prediction':False,
            'candidate_summary':summary,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'python':platform.python_version(),'numpy':np.__version__,'elapsed_s':time.monotonic()-start,
            'source_hashes':{str(p):sha(p) for p in sources},'artifact_hashes':{str(p):sha(p) for p in out.iterdir()},
            'parent_binding_checks':bindings,'gpu_jobs_started':0,'production_cuda_modified':False}
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'tests':tests.testsRun,'summary':summary},indent=2))


if __name__=='__main__':main()
