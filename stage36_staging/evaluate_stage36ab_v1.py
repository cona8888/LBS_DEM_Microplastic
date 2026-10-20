import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import refined_ib_sphere_v1 as m
import verify_stage36q_nonzero_reference_v1 as ref
from verify_stage36r_manufactured_flow_v1 import gint
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def main():
    raw=ROOT/'stage36_evaluations/stage36ab_source_gap_20260909/verification_01';base=ROOT/'stage36_evaluations/stage36w_spatial_flow_20260908/verification_01';rv=json.loads((raw/'manifest.json').read_text());bv=json.loads((base/'manifest.json').read_text());assert rv['completed'] and rv['diagnostic_only'] and not (raw/'failure.json').exists()
    for root,v in ((raw,rv),(base,bv)):
        for group in ('source_hashes','parent_hashes','artifact_hashes'):
            for p,h in v[group].items():assert sha(p)==h,p
    F0=4*np.pi/3*.1*.2**3*2*.01/.2**2;Iref=F0*gint(1);n=24;dt=1/n**2;x=(np.indices((n,n,n)).reshape(3,-1).T+.5)/n-.5;r=np.linalg.norm(x,axis=1);ext=r>ref.R;u0=ref.field(x);scale=np.sqrt(np.mean(np.sum(u0[ext]**2,axis=1)))
    br=next(r for r in bv['cases'] if r['n']==24);bh=json.loads((base/'n24_history.json').read_text());rows=[]
    with np.load(base/'n24_states.npz') as z:
        a=z['quarter_4'].reshape(19,-1);up=(m.C.T@a).T/a.sum(axis=0)[:,None]*n
    rows.append({'gap_cells':0,'equations':'manufactured','final_velocity_discrepancy':max(br['quarter_velocity_errors']),'max_force_discrepancy':br['max_force_error'],'max_interior_source_relative':br['max_interior_source_force_relative'],'source_impulse_relative':float(dt*sum(e.get('source_integral',[0])[0] for e in bh)/Iref) if 'source_integral' in bh[0] else None,'final_mean_exterior_velocity_x':float(up[ext,0].mean())})
    for case in rv['cases']:
        g=case['gap_cells'];h=json.loads((raw/f'gap{g}_history.json').read_text());assert len(h)==n*n and all(np.max(np.abs(e['momentum_residual']))/n**3<1e-12 for e in h)
        for suffix in ('first','states','source_taper'):assert (raw/f'gap{g}_{suffix}.npz').exists()
        rows.append({'gap_cells':g,'equations':'perturbed diagnostic','final_velocity_discrepancy':case['quarter_velocity_discrepancies'][-1]['rms'],'max_force_discrepancy':case['max_force_discrepancy'],'max_interior_source_relative':case['max_interior_source_force_relative'],'source_impulse_relative':float(dt*sum(e['source_integral'][0] for e in h)/Iref),'final_mean_exterior_velocity_x':case['quarter_velocity_discrepancies'][-1]['mean_velocity'][0]})
    out=raw.parent/'analysis_01';out.mkdir(exist_ok=False);(out/'comparison.json').write_text(json.dumps(rows,indent=2))
    gaps=[r['gap_cells'] for r in rows];fig,ax=plt.subplots(1,3,figsize=(12,3.7))
    ax[0].plot(gaps,[100*r['final_velocity_discrepancy'] for r in rows],'o-');ax[0].set(ylabel='Final velocity discrepancy (%)',title='Original-field comparator')
    ax[1].plot(gaps,[100*r['max_force_discrepancy'] for r in rows],'o-');ax[1].set(ylabel='Maximum force discrepancy (%)',title='Original-force comparator')
    ax[2].semilogy(gaps,[max(r['max_interior_source_relative'],1e-16) for r in rows],'o-');ax[2].set(ylabel='Interior-source term / force scale',title='Overlap diagnostic')
    for a in ax:a.set_xlabel('Numerical source gap (cells)');a.set_xticks(gaps);a.grid(alpha=.25)
    fig.suptitle('Stage36AB: source-gap sensitivity — gapped equations are not validation cases');fig.tight_layout();fig.savefig(out/'gap_sensitivity.png',dpi=160);plt.close(fig)
    lines=['# Stage36AB — source/interface gap sensitivity','', 'Two new N24 diagnostic flows completed with all health and exact momentum-ledger checks passing. The gapped equations do not share the baseline analytical solution, so their discrepancies cannot be assessed against the 2% validation gate.','', '| Gap | Interior-source term | Final velocity discrepancy | Maximum force discrepancy |','|---|---:|---:|---:|']
    for q in rows:lines.append(f"| {q['gap_cells']} cells | {q['max_interior_source_relative']:.3e} | {q['final_velocity_discrepancy']:.2%} | {q['max_force_discrepancy']:.2%} |")
    lines+=['','A one-cell gap reduces the interpolated interior-source term from 11.38% of the force scale to approximately 5e-13, yet velocity and force discrepancies become much larger. The two-cell result is also worse than baseline and is nonmonotonic relative to one cell. Therefore source/interface overlap is not the sole cause; in the original discretization it partly compensates other source, boundary-enforcement and force-extraction errors.','', 'Do not remove the overlap correction or adopt a gap. The next defensible step is to stop perturbing this compact manufactured solution and formulate an independently derived, discretely compatible nonzero-force benchmark—or compare against a separate established immersed-boundary implementation—before changing the production solver. Permeability, drag and release fraction remain unqualified.']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8');(out/'manifest.json').write_text(json.dumps({'completed':True,'diagnostic_only':True,'source_hash':sha(__file__),'parent_hashes':{str(raw/'manifest.json'):sha(raw/'manifest.json'),str(base/'manifest.json'):sha(base/'manifest.json')},'artifact_hashes':{str(p):sha(p) for p in out.iterdir()},'release_qualified':False},indent=2));print('\n'.join(lines).encode('ascii','replace').decode())
if __name__=='__main__':main()
