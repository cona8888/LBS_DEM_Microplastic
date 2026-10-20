import io,json,unittest,platform
from pathlib import Path
import numpy as np
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
def transfer(total,solid,chi,volume,dt):
    total=np.asarray(total,float);solid=np.asarray(solid,float);chi=np.asarray(chi,float)
    if total.ndim!=2 or total.shape[1]!=3 or solid.shape!=total.shape or chi.shape!=(len(total),):raise ValueError('shape')
    if not all(np.isfinite(a).all() for a in (total,solid,chi)) or np.any((chi<0)|(chi>1)) or not np.isfinite(volume*dt) or volume<=0 or dt<=0:raise ValueError('invalid input')
    fluid=total-solid
    if np.any(solid[chi==0]!=0) or np.any(fluid[chi==1]!=0):raise ValueError('source assigned to absent phase')
    return dt*volume*fluid,dt*volume*solid
class Tests(unittest.TestCase):
    def test_conservation(self):
        b=np.array([[1.,2,3]]);s=b*.3;f,i=transfer(b,s,[.5],.2,.1);np.testing.assert_allclose(f+i,b*.02,rtol=0,atol=1e-12)
    def test_exterior(self):
        f,s=transfer([[1,0,0]],[[0,0,0]],[.7],1,1);self.assertEqual(float(s.sum()),0);self.assertEqual(float(f.sum()),1)
    def test_solid(self):
        f,s=transfer([[2,0,0]],[[2,0,0]],[1],1,1);self.assertEqual(float(f.sum()),0);self.assertEqual(float(s.sum()),2)
    def test_fraction(self):
        with self.assertRaises(ValueError):transfer([[1,0,0]],[[0,0,0]],[1.1],1,1)
    def test_absent_phase(self):
        with self.assertRaises(ValueError):transfer([[1,0,0]],[[0,0,0]],[1],1,1)
    def test_units(self):
        a,b=transfer([[1,0,0]],[[0,0,0]],[0],2,3);self.assertEqual(a[0,0],6)
    def test_information_loss(self):
        # Same summed impulse, two different valid allocations: sum is not invertible.
        a,b=transfer([[1,0,0]],[[0,0,0]],[.5],1,1);c,d=transfer([[1,0,0]],[[1,0,0]],[.5],1,1)
        np.testing.assert_array_equal(a+b,c+d);self.assertFalse(np.array_equal(b,d))
def main():
    parent=ROOT/'stage36_evaluations/stage36t_cell_integration_20260908/analysis_01/manifest.json';v=json.loads(parent.read_text());assert v['completed'];checked={str(parent):sha(parent)}
    for group in ('source_hashes','input_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h;checked[p]=h
    out=ROOT/'stage36_evaluations/stage36u_phase_transfer_20260908/verification_01';out.mkdir(parents=True,exist_ok=False)
    log=io.StringIO();test=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));(out/'tests.txt').write_text(log.getvalue());assert test.wasSuccessful()
    rows=[]
    for phase in (0,.13,.37):
        for k in (2,4,8):
            p=parent.parent/f'phase{phase}_k{k}.npz'
            with np.load(p) as z:
                b=z['cell_source'];s=z['joint_interior_source'];chi=z['solid_fraction'];fluid,solid=transfer(b,s,chi,1/4096,1/256)
                residual=float(np.max(abs(fluid+solid-b/(4096*256))));assert residual<1e-15 and np.max(abs(solid))==0
                rows.append({'phase':phase,'subdivisions':k,'max_cell_conservation_residual':residual,'solid_impulse_norm':float(np.linalg.norm(solid.sum(axis=0)))})
    (out/'results.json').write_text(json.dumps({'unit_tests':test.testsRun,'packets':rows,'flow_runs':0},indent=2))
    (out/'RESULTS.md').write_text('# Stage36U — phase-separated transfer prototype\n\nSeven algebraic tests and nine saved source packets passed. Separate fluid/solid impulse registers preserve total source impulse and the prescribed zero interior source. This is by-construction bookkeeping, not a hydrodynamic accuracy result.\n\nA counterexample confirms that a single summed momentum increment cannot recover arbitrary fluid/solid allocations. The existing single-population LBM cannot adopt these two registers merely by changing its force subtraction. We have not implemented streaming, pressure, viscous exchange or small-cut-cell stabilization for this representation.\n\nDecision: do not patch this prototype into production or claim the previous error is solved. Next requires choosing a compatible spatial discretization (or testing another verified boundary-compatible formulation), then repeating the frozen nonzero-force benchmark. This is a solver-design decision, not another source-quadrature adjustment. Original failures remain. No flow, drag-validation or release simulation was run.\n',encoding='utf-8')
    contract=ROOT/'stage36_staging/STAGE36U_PHASE_TRANSFER_CONTRACT.md'
    (out/'manifest.json').write_text(json.dumps({'completed':True,'unit_tests_passed':test.testsRun,'source_packets_checked':9,'source_hashes':{str(Path(__file__).resolve()):sha(__file__),str(contract):sha(contract),str(ROOT/'stage36_staging/verify_stage36d_wrench_transfer_v1.py'):sha(ROOT/'stage36_staging/verify_stage36d_wrench_transfer_v1.py')},'input_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'python':platform.python_version(),'numpy':np.__version__,'flow_solver_integration_qualified':False,'release_qualified':False},indent=2));print('7 tests,9 packets passed; no flow solver integration')
if __name__=='__main__':main()
