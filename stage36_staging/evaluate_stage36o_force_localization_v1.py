"""Read-only physics evidence analysis, writing only a new derived directory."""
import json,hashlib,platform,unittest,io
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('C:/MATDEM_MICROPLASTIC')
BASE=ROOT/'stage36_evaluations/stage36o_force_localization_20260908'
STARTS=(0,.0625,.125,.25,.5)
JS=4*np.pi*.2**3/3*.02
FS=6*np.pi*.1*.2*.02
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def dump(p,d):Path(p).write_text(json.dumps(d,indent=2),encoding='utf-8')
def cumulative(a,s):return np.vstack([np.zeros(3),np.cumsum(a,axis=0)[s-1::s]])
def windows(a,b):
    delta=b-a;rows=[]
    for start in STARTS:
        i=round(start*256);q=delta[i:]-delta[i];norm=np.linalg.norm(q,axis=1);j=int(np.argmax(norm))
        force=np.diff(delta[i:],axis=0)*256
        rows.append({'start':start,'peak_impulse_difference':float(norm[j]/JS),'peak_time':(i+j)/256,'final_signed_difference':q[-1].tolist(),'force_rms_difference':float(np.sqrt(np.mean(np.sum(force**2,axis=1)))/FS)})
    return rows
class Tests(unittest.TestCase):
    def test_binning(self):np.testing.assert_array_equal(cumulative(np.ones((512,3)),2)[-1],np.ones(3)*512)
    def test_zero(self):self.assertTrue(all(r['peak_impulse_difference']==0 for r in windows(np.zeros((257,3)),np.zeros((257,3)))))
    def test_window(self):
        a=np.zeros((257,3));b=a.copy();b[1:,0]=1
        r=windows(a,b);self.assertAlmostEqual(r[0]['peak_impulse_difference'],1/JS);self.assertEqual(r[0]['peak_time'],1/256);self.assertEqual(r[1]['peak_impulse_difference'],0)
    def test_vector(self):
        a=np.zeros((257,3));b=a.copy();b[:,0]=1;b[:,1]=-1;b[0]=0
        self.assertAlmostEqual(windows(a,b)[0]['peak_impulse_difference'],np.sqrt(2)/JS)
def main():
    checked={};datasets={};audit=[]
    handoff=ROOT/'stage36_evaluations/stage36n_kinetic_20260908/render_01/next_gate.json';h=read(handoff)
    assert sha(h['evidence_manifest'])==h['evidence_sha256'];assert not h['refinement_qualified'];checked[str(handoff)]=sha(handoff)
    for label,folder in [('equilibrium','stage36m_refinement_20260908'),('kinetic','stage36n_kinetic_20260908')]:
        raw=ROOT/'stage36_evaluations'/folder/'verification_01';manifest=raw/'verification.json';v=read(manifest);assert v['execution_completed'] and v['unit_tests_passed'];assert not (raw/'failure.json').exists();checked[str(manifest)]=sha(manifest)
        for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
            for p,digest in v[group].items():assert sha(p)==digest,p;checked[p]=digest
        datasets[label]={}
        for s in (1,2,4):
            hist=read(raw/f's{s}_m56_history.json');assert len(hist)==256*s
            get=lambda key:np.array([r[key] for r in hist],float)
            P0=get('momentum_before');P1=get('momentum_after');Q0=get('interior_momentum_before');Q1=get('interior_momentum_after')
            np.testing.assert_allclose(P0[1:],P1[:-1],atol=1e-12,rtol=0);np.testing.assert_allclose(Q0[1:],Q1[:-1],atol=1e-12,rtol=0)
            scale=s/256;boundary=-get('force_on_fluid')*scale;interior=(Q1-Q0)*scale;candidate=get('force_candidate')*scale
            assert np.isfinite(candidate).all();np.testing.assert_allclose(candidate,boundary+interior,atol=1e-12,rtol=0)
            cum=cumulative(candidate,s);exterior=-((P1-Q1)-(P0[0]-Q0[0]))*scale;exterior=np.vstack([np.zeros(3),exterior[s-1::s]])
            residual=float(np.max(abs(cum-exterior)));assert residual<1e-10
            datasets[label][s]={'candidate':cum,'boundary':cumulative(boundary,s),'interior':cumulative(interior,s)}
            audit.append({'initialization':label,'s':s,'steps':len(hist),'exterior_momentum_identity_max_residual':residual})
    log=io.StringIO();test=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));assert test.wasSuccessful(),log.getvalue()
    out=BASE/'analysis_01';out.mkdir(parents=True,exist_ok=False);(out/'tests.txt').write_text(log.getvalue())
    results=[]
    for label,d in datasets.items():
        for lo,hi in ((1,2),(2,4)):
            for component in ('candidate','boundary','interior'):
                results.append({'initialization':label,'pair':[lo,hi],'component':component,'windows':windows(d[lo][component],d[hi][component])})
    dump(out/'localization.json',{'audit':audit,'results':results,'starts':STARTS,'impulse_scale':JS,'force_scale':FS})
    fig,axs=plt.subplots(1,2,figsize=(11,4.8));fig.subplots_adjust(top=.81,bottom=.22,wspace=.32)
    for label,color in [('equilibrium','#ba625d'),('kinetic','#287c8a')]:
        d=datasets[label];delta=d[4]['candidate']-d[2]['candidate'];axs[0].plot(np.arange(257)/256,100*np.linalg.norm(delta,axis=1)/JS,label=label,color=color)
        row=next(r for r in results if r['initialization']==label and r['pair']==[2,4] and r['component']=='candidate')
        axs[1].plot(STARTS,[100*w['peak_impulse_difference'] for w in row['windows']],'o-',label=label,color=color)
    axs[0].set(xlabel='Time (reference units)',ylabel='Cumulative impulse discrepancy (%)',title='Fine pair: original whole history')
    axs[1].set(xlabel='Diagnostic window start (end = 1)',ylabel='Re-zeroed peak discrepancy (%)',title='Windowing is diagnostic, not acceptance')
    for ax in axs:ax.axhline(2,ls=':',color='gray');ax.legend(frameon=False);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Stage36O | Where does the force discrepancy accumulate?',fontsize=15)
    fig.text(.08,.05,'Existing six trajectories only; no new flow runs. Momentum identity is an accounting check, not physical drag validation.\nOriginal whole-history refinement failure remains in force.',fontsize=9)
    fig.savefig(out/'force_localization.png',dpi=170);plt.close(fig)
    table=[]
    for r in results:
        if r['component']=='candidate':
            for w in r['windows']:table.append(f"| {r['initialization']} | {r['pair'][0]} to {r['pair'][1]} | {w['start']} | {100*w['peak_impulse_difference']:.4f}% | {w['peak_time']:.4f} | {100*w['force_rms_difference']:.4f}% |")
    report='''# Stage36O — force-discrepancy localization

Completed read-only analysis of six existing time-scaled trajectories. Four new analysis tests passed; this did not rerun the prior151 solver tests or create new flow simulations. All recorded input hashes were checked. Candidate cumulative impulse independently reconstructed from total-minus-interior momentum within1e-10 physical impulse. This identity shares the computed flow and interior quadrature: it verifies accounting, NOT surface traction accuracy.

## Fixed diagnostic windows

| Initialization | Pair | Window start | Peak re-zeroed impulse difference | Peak time | Window force RMS difference |
|---|---|---:|---:|---:|---:|
'''+ '\n'.join(table)+'''

Impulse and force percentages have different fixed reference scales, matching Stage36M/N. Every window ends at1; values are vector norms. Shorter windows integrate less time and are not alternative acceptance criteria. Full signed boundary/interior contributions are retained in localization.json. Their errors may cancel, so they must not be added as magnitudes.

## Claim boundary and next gate

The original whole-history force-refinement failure remains. Window localization alone cannot identify its cause or justify removing startup. No claim of validated drag or release fraction follows from this balance identity. The next experimental-in-code question is a compatible-start, smoothly driven periodic-sphere benchmark. Before execution, its prescribed loading, treatment of periodic mean momentum, external forcing inside the fictitious fluid, and independent traction comparator must be mathematically consistent. An isolated unbounded Stokes drag formula is not automatically a valid comparator for the present finite periodic box or transient shear.

No production, mobile sand, fibre motion, migration, clogging or coupling was executed. Reproduce with stage36_staging/evaluate_stage36o_force_localization_v1.py; existing output directories are refused.
'''
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    dump(out/'next_gate.json',{'scope':'define compatible-start periodic sphere forcing and independent force comparator before bounded execution','force_refinement_qualified':False,'production_execution_authorized':False,'release_prediction_qualified':False})
    sources={str(Path(__file__).resolve()):sha(__file__),str(ROOT/'stage36_staging/STAGE36O_FORCE_LOCALIZATION_CONTRACT.md'):sha(ROOT/'stage36_staging/STAGE36O_FORCE_LOCALIZATION_CONTRACT.md')}
    for p,digest in checked.items():assert sha(p)==digest
    dump(out/'manifest.json',{'completed':True,'new_flow_runs':0,'analysis_tests_passed':test.testsRun,'input_hashes':checked,'source_hashes':sources,'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'python':platform.python_version(),'numpy':np.__version__,'utc':datetime.now(timezone.utc).isoformat()})
    print(json.dumps([r for r in results if r['component']=='candidate' and r['pair']==[2,4]],indent=2));print(out)
if __name__=='__main__':main()
