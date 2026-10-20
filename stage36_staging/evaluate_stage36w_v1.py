import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import refined_ib_sphere_v1 as m
import verify_stage36q_nonzero_reference_v1 as ref
from verify_stage36r_manufactured_flow_v1 import ramp
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def main():
    raw=ROOT/'stage36_evaluations/stage36w_spatial_flow_20260908/verification_01'
    v=json.loads((raw/'manifest.json').read_text());assert v['completed'] and not (raw/'failure.json').exists()
    for group in ('source_hashes','parent_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h,p
    out=raw.parent/'analysis_01';out.mkdir(exist_ok=False)
    fig,ax=plt.subplots(1,2,figsize=(10,4));diagnostics=[]
    F0=4*np.pi/3*.1*.2**3*2*.01/.2**2
    for row in sorted(v['cases'],key=lambda r:r['n']):
        n=row['n'];h=json.loads((raw/f'n{n}_history.json').read_text());assert len(h)==n*n
        np.testing.assert_allclose(np.array([r['unsubtracted_force'] for r in h])-np.array([r['interior_source_force'] for r in h]),[r['force'] for r in h],atol=1e-15,rtol=0)
        x=(np.indices((n,n,n)).reshape(3,-1).T+.5)/n-.5;r=np.linalg.norm(x,axis=1);ext=r>ref.R;mask=(r>ref.R)&(r<ref.L);u0=ref.field(x)
        errors=[]
        with np.load(raw/f'n{n}_states.npz') as z:
            for q in range(1,5):
                a=z[f'quarter_{q}'].reshape(19,-1);u=(m.C.T@a).T/a.sum(axis=0)[:,None]*n
                errors.append(float(np.sqrt(np.mean(np.sum((u[ext]-ramp(q/4)[0]*u0[ext])**2,axis=1)))/np.sqrt(np.mean(np.sum(u0[ext]**2,axis=1)))))
        np.testing.assert_allclose(errors,row['quarter_velocity_errors'],rtol=0,atol=1e-14)
        G,lap=ref.derivatives(x[mask]);source=np.zeros_like(x);source[mask]=np.einsum('nij,nj->ni',G,u0[mask])-.1*lap
        quads=[]
        for counts in ((4,8,16),(8,16,32)):
            body,w=m.ib.sphere_quadrature(n/5,*counts);quads.append((w@m.trilinear(source,body+n/2,n)/n**3).tolist())
        diagnostics.append({'n':n,'steady_total_source':(source.sum(axis=0)/n**3).tolist(),'interior_source_quadratures':quads})
        ax[0].plot([r['time'] for r in h],np.array([r['force'] for r in h])[:,0]/F0,label=f'{n} cubed')
        ax[1].plot([.25,.5,.75,1],np.array(errors)*100,'o-',label=f'{n} cubed')
    ax[0].plot([r['time'] for r in h],np.array([r['exact_force'] for r in h])[:,0]/F0,'k--',label='Analytical')
    ax[0].set(xlabel='Reference time',ylabel='Force / final analytical force',title='Complete source-aware force')
    ax[1].axhline(2,color='k',ls='--',label='2% gate');ax[1].set(xlabel='Reference time',ylabel='Exterior velocity RMS error (%)',title='Field error grows with refinement')
    for a in ax:a.legend();a.grid(alpha=.25)
    fig.suptitle('Stage36W: manufactured-flow verification — NOT qualified');fig.tight_layout();fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
    (out/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
    lines=['# Stage36W — combined diffusive refinement','', 'Three bounded CPU flows completed. N16 exactly reproduced Stage36R s1 histories and saved arrays. All runtime health gates passed; all analytical gates failed.','', '| Grid | Maximum force error | Worst-quarter velocity error |','|---|---:|---:|']
    for r in sorted(v['cases'],key=lambda r:r['n']):lines.append(f"| {r['n']}³ | {r['max_force_error']:.2%} | {max(r['quarter_velocity_errors']):.2%} |")
    lines+=['','The frozen threshold is 2% for both observables. Refinement does not demonstrate convergence: field errors increase. Do not expand production or claim qualified drag/release. Next: inspect source splitting and manufactured-field/interface consistency against this unchanged comparator before any further flow campaign.','', 'This changes space, time step and marker count together; no formal spatial order is inferred. Separate steady source quadrature diagnostics are saved. Numerical verification is not experimental validation.']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'completed':True,'parent':sha(raw/'manifest.json'),'source':sha(__file__),'artifacts':{str(p):sha(p) for p in out.iterdir()},'analytical_passed':False},indent=2))
    print('\n'.join(lines))
if __name__=='__main__':main()
