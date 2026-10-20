import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
from evaluate_render_stage36l_v1 import eq,close
from body_link_extractor_v1 import C
BASE=ROOT/'stage36_evaluations/stage36r_manufactured_flow_20260908';raw=BASE/'verification_01'
def main():
    v=json.loads((raw/'manifest.json').read_text());assert v['completed'] and not (raw/'failure.json').exists()
    for group in ('source_hashes','parent_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h
    fig,ax=plt.subplots(figsize=(8,4.7));allh=[]
    for r in v['cases']:
        s=r['s'];h=json.loads((raw/f's{s}_history.json').read_text());assert len(h)==256*s
        for row in h:close(np.array(row['unsubtracted_force'])-row['interior_source_force'],row['force'],1e-12)
        with np.load(raw/f's{s}_first.npz') as z:
            old=z['before_source'].reshape(19,-1);forced=z['old'].reshape(19,-1);rho=old.sum(axis=0);u=C.T@old/rho
            close(forced-old,eq(rho,u+(z['source_impulse']/rho[:,None]).T)-eq(rho,u),1e-14)
            close((C.T@(forced-old)).T,z['source_impulse'],1e-14)
        ax.plot([q['time'] for q in h],[q['force'][0] for q in h],label=f's={s}');allh.append(h)
    h=allh[-1];ax.plot([q['time'] for q in h],[q['exact_force'][0] for q in h],'k--',label='Analytical traction');ax.set(xlabel='Time (reference units)',ylabel='x force (reference units)',title='Stage36R | Stable runs fail the manufactured solution');ax.legend(frameon=False);fig.tight_layout()
    out=BASE/'analysis_01';out.mkdir(exist_ok=False);fig.savefig(out/'force_comparison.png',dpi=160);plt.close(fig)
    table='\n'.join(f"| {r['s']} | {100*r['max_force_error']:.2f}% | {100*max(r['quarter_velocity_errors']):.2f}% | {100*r['max_interior_source_force_relative']:.2f}% |" for r in v['cases'])
    report='''# Stage36R — first nonzero manufactured-force solver test

Three bounded CPU runs completed. All per-step positivity, density, mass, marker-slip and source-plus-interface momentum checks passed. **All three analytical comparisons failed** the frozen2% gates. No prior regression suite was rerun. Source injection was independently reconstructed from saved first-step populations, and recorded force subtraction checked at every step. This audit does not constitute an independent reimplementation of the whole solver.

| Time factor | Peak force error / steady reference | Worst quarter velocity RMS / final reference RMS | Interior source quadrature / force reference |
|---|---:|---:|---:|
'''+table+'''

The fixed N16 grid has only3.2 cells across the manufactured shell thickness. A large interior source correction appears despite the continuum source being zero inside the sphere: interpolation across the surface samples exterior forcing. This is evidence of a source/geometry discretization concern, not proof of the sole cause. Decreasing time step alone does not recover the reference velocity field. Stable conservation and no-slip tests are insufficient to establish physical accuracy.

Next: audit cell-centre source integration and interior leakage against the analytical shell integral across spatial resolutions before further flow runs. Keep the analytical reference and thresholds unchanged. The previous3.68% force sensitivity is not resolved. No release, drag validation or production claims are qualified.
'''
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'audit_completed':True,'analytical_passed':False,'source_hashes':{str(Path(__file__).resolve()):sha(__file__),str(raw/'manifest.json'):sha(raw/'manifest.json'),str(ROOT/'stage36_staging/evaluate_render_stage36l_v1.py'):sha(ROOT/'stage36_staging/evaluate_render_stage36l_v1.py')},'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()}},indent=2))
    print(report)
if __name__=='__main__':main()
