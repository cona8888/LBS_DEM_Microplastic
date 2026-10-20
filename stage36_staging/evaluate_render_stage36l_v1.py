"""Independent endpoint/first-step audit of split IBM reference, not drag validation."""
import json
from pathlib import Path
import numpy as np
from scipy.interpolate import interpn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
from body_link_extractor_v1 import C

BASE=ROOT/'stage36_evaluations/stage36l_full_ib_sphere_20260908';RAW=BASE/'verification_01'
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def close(a,b,tol=1e-9):np.testing.assert_allclose(a,b,rtol=0,atol=tol)
def eq(rho,u):
    w=np.array([1/3]+[1/18]*6+[1/36]*12);cu=C@u
    return w[:,None]*rho*(1+3*cu+4.5*cu**2-1.5*np.sum(u*u,axis=0))
def kernel(r):
    a=np.abs(r);p=np.zeros_like(a);s=a<=1;t=(a>1)&(a<2)
    p[s]=(3-2*a[s]+np.sqrt(1+4*a[s]-4*a[s]**2))/8;p[t]=(5-2*a[t]-np.sqrt(-7+12*a[t]-4*a[t]**2))/8
    return p
def integral(f,c,R,fine=False):
    n=f.shape[1];nr,nmu,nt=(8,16,32) if fine else (4,8,16);rr,wr=np.polynomial.legendre.leggauss(nr);mu,wm=np.polynomial.legendre.leggauss(nmu)
    points=[];weights=[]
    for i in range(nr):
        r=R*(1+rr[i])/2
        for j in range(nmu):
            for k in range(nt):
                th=2*np.pi*k/nt;points.append(c+r*np.array([np.sqrt(1-mu[j]**2)*np.cos(th),np.sqrt(1-mu[j]**2)*np.sin(th),mu[j]]));weights.append(wr[i]*R/2*wm[j]*2*np.pi/nt*r*r)
    a=f.reshape(19,-1);field=np.column_stack((a.sum(axis=0),(C.T@a).T)).reshape(n,n,n,4);axis=np.arange(n)+.5
    return np.array(weights)@interpn((axis,axis,axis),field,np.array(points))

def main():
    v=read(RAW/'verification.json');assert v['execution_completed'] and v['flow_conditions']==12 and v['unit_tests_run']==141 and v['disabled_control_detected'];assert not (RAW/'failure.json').exists()
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for p,h in v[group].items():assert sha(p)==h,p
    rows=v['cases'];audits=[];histories={}
    for r in rows:
        name=r['case_id'];n=r['n'];R=r['radius_lu'];U=np.array([r['direction']*.08/n,0,0]);h=read(RAW/(name+'_history.json'));histories[name]=h;assert len(h)==n*n
        assert read(RAW/(name+'_result.json'))==r
        with np.load(RAW/(name+'_states.npz')) as z:
            for key in ('initial','final'):
                f=z[key];assert np.isfinite(f).all() and np.all(f>0);inside=integral(f,z['centre_'+key],R)
                row=h[0] if key=='initial' else h[-1];suffix='before' if key=='initial' else 'after'
                close(f.sum(),row['mass_'+suffix]);close(inside[0],row['interior_mass_'+suffix]);close(inside[1:],row['interior_momentum_'+suffix])
                close((C.T@f.reshape(19,-1)).sum(axis=1),row['momentum_'+suffix])
            fine=integral(z['final'],z['centre_final'],R,True)[0];close(abs(fine-h[-1]['interior_mass_after'])/r['initial_exterior_mass'],r['final_exterior_quadrature_discrepancy'],1e-12)
        ledger=0.
        for t,a in enumerate(h):
            assert a['step']==t+1;close(np.array(a['centre_after'])-a['centre_before'],U)
            close(a['exterior_mass_before'],a['mass_before']-a['interior_mass_before']);close(a['exterior_mass_after'],a['mass_after']-a['interior_mass_after'])
            dp=np.array(a['momentum_after'])-a['momentum_before'];di=np.array(a['interior_momentum_after'])-a['interior_momentum_before'];I=np.array(a['force_on_fluid'])
            close(a['force_candidate'],-I+di);close(a['momentum_ledger_residual'],dp-I);ledger=max(ledger,float(np.max(np.abs(dp-I)))/r['initial_total_mass'])
            if t:close(a['mass_before'],h[t-1]['mass_after']);close(a['momentum_before'],h[t-1]['momentum_after'])
        metrics={'total':max(a['total_mass_relative_drift'] for a in h),'exterior':max(abs(a['exterior_mass_after']-r['initial_exterior_mass'])/r['initial_exterior_mass'] for a in h),'slip':max(a['marker_slip'] for a in h),'probe':max(a['probe_slip'] for a in h)/(.02/n)}
        close(metrics['total'],r['max_total_mass_drift'],1e-15);close(metrics['exterior'],r['max_exterior_mass_drift'],1e-15);close(metrics['probe'],r['max_probe_slip_over_amplitude'],1e-12)
        assert r['gates']['total_mass']==(metrics['total']<=1e-10);assert r['gates']['exterior_mass_estimate']==(metrics['exterior']<=1e-6);assert r['gates']['marker_no_slip']==(metrics['slip']<=1e-10)
        if r['perturb']:assert r['gates']['probe_no_slip']==(metrics['probe']<=.05)
        with np.load(RAW/(name+'_firststep.npz')) as z:
            f=z['old'];a=f.reshape(19,-1);rho=a.sum(axis=0);post=(a-(a-eq(rho,C.T@a/rho))/.8).reshape(f.shape)
            expected=np.empty_like(f)
            for k in range(19):
                # Independent index gather, not the solver's np.roll.
                idx=np.indices((n,n,n));idx=(idx-C[k,:,None,None,None])%n;expected[k]=post[k][tuple(idx)]
            close(expected,z['streamed'],1e-14)
            grid=np.array(list(np.ndindex(n,n,n)),float)+.5;J=np.ones((r['marker_count'],n**3))
            for d in range(3):J*=kernel(grid[None,:,d]-z['markers'][:,None,d])
            sf=z['streamed'].reshape(19,-1);rho=sf.sum(axis=0);u=(C.T@sf).T/rho[:,None];lam=z['marker_impulses'];imp=J.T@lam
            close(imp,z['grid_impulse'],1e-12)
            if r['interface_enabled']:close((J/rho)@J.T@lam,U-J@u,1e-12)
            else:close(lam,0,1e-15)
            expected=sf+eq(rho,(u+imp/rho[:,None]).T)-eq(rho,u.T);close(expected,z['new'].reshape(19,-1),1e-13)
            close(lam.sum(axis=0),h[0]['force_on_fluid']);close(float(np.max(np.abs(J@(u+imp/rho[:,None])-U))),h[0]['marker_slip'],1e-12)
        audits.append({'case_id':name,'endpoint_geometry_integrals_checked':True,'first_full_step_independently_reconstructed':True,'history_ledger_relative_max':ledger})
    out=BASE/'render_01';out.mkdir(exist_ok=False);dump(out/'independent_audit.json',{'audit_passed':True,'cases':audits,'physical_drag_validated':False})
    uniform=[r for r in rows if not r['perturb']];active=[r for r in rows if r['perturb'] and r['interface_enabled']];disabled=rows[-1]
    table='\n'.join(f"| {r['case_id']} | {r['max_total_mass_drift']:.2e} | {r['max_exterior_mass_drift']:.2e} | {r['max_marker_slip']:.2e} | {r['max_probe_slip_over_amplitude']:.3f} | {', '.join(k for k,b in r['gates'].items() if not b) or 'none'} |" for r in rows)
    report=f'''# Stage36L — full CPU immersed-sphere integration

141 unit tests passed. All12 planned CPU flow conditions completed. {sum(r['passed'] for r in uniform)}/{len(uniform)} uniform cases passed every frozen gate. {sum(r['passed'] for r in active)}/{len(active)} active nonuniform cases passed every gate. The disabled-interface control was correctly detected by boundary slip. No threshold was relaxed.

| Case | Total mass drift | Exterior mass estimate drift | Marker slip (LU) | Probe slip / amplitude | Failed gates |
|---|---:|---:|---:|---:|---|
{table}

## What was implemented

Complete periodic D3Q19 BGK collision and streaming on an always-active grid, followed by a solved endpoint immersed-boundary impulse and an equilibrium-difference population update. The impulse is determined from the kernel-overlap matrix, not from tuned feedback gain. A full-step saved audit independently reconstructs streaming, the coupling matrix, impulse equation and populations for all12 cases. Initial/final geometric interior integrals use a separately implemented trilinear interpolator. All time-series ledgers and frozen source/artifact/parent hashes were checked. Full fields are archived at endpoints and the first step, not every step.

The mass outside the sphere is estimated from actual simulated density: total mass minus a geometric volume quadrature, not binary cell counts. A finer final quadrature cross-check is recorded. This is still an approximate integral and not an exact cut-cell flux audit. Force is the negative applied fluid impulse plus the measured interior-momentum change; balance closure alone does not validate physical drag.

## Interpretation and limits

Uniform co-motion now passes the integration check without deleting/refilling cells. The active tests are necessary because a disabled sphere also preserves uniform flow. Near-zero enforced-marker slip does not ensure no-slip between markers: separate off-marker probes test that weakness. No continuum solution is available here for the nonuniform transient force, so no drag or release claim is made. Stage36J's old method remains failed; its immutable evidence is not replaced.

This is a new endpoint operator-split reference, not a Guo half-force implementation or reproduction of a published IBM solver. Force time integration, effective boundary location, marker-spacing sensitivity, nonzero-drag accuracy and time-step convergence remain unqualified. No sand, mobile fibres, migration, clogging, two-way body dynamics or production simulation was launched.

Literature context: [Uhlmann (2005), Appendix B](https://arxiv.org/html/1809.08170v1) motivates interior-fluid momentum accounting. [Kupershtokh et al. (2009)](https://doi.org/10.1016/j.camwa.2009.02.024) provides equilibrium-difference forcing context; using that update does not establish this split scheme's continuum accuracy.

## Next gate

Resolve the failed active-test gates, if any, with targeted boundary-resolution and geometric-flux diagnostics. Independently vary marker spacing and time step before comparing physical drag against an established sphere benchmark. Do not promote on marker constraints or uniform-flow conservation alone. No fibre-release execution is authorized.

Reproduction entry points: stage36_staging/verify_stage36l_full_ib_v1.py and evaluate_render_stage36l_v1.py, using the installed Python3.12 interpreter and OPENBLAS_NUM_THREADS=1. Existing output directories are refused. Inputs, dependencies and data are bound by verification_01/verification.json; the figure and audit are bound by render_manifest.json.
'''
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    dump(out/'next_gate.json',{'evidence_manifest':str(RAW/'verification.json'),'evidence_sha256':sha(RAW/'verification.json'),'uniform_cases_passed':all(r['passed'] for r in uniform),'active_cases_passed':all(r['passed'] for r in active),'next_scope':'targeted active-test boundary resolution and geometric-flux diagnostics, then marker/time refinement and drag benchmark','production_execution_authorized':False,'release_prediction_qualified':False})
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False});fig,axs=plt.subplots(2,2,figsize=(12,9));fig.subplots_adjust(top=.83,bottom=.16,hspace=.5,wspace=.32)
    fig.suptitle('Stage36L | The interface is now part of a complete flow step',fontsize=18,y=.96)
    fig.text(.07,.90,f'141 tests passed | 12 CPU runs completed | Uniform: {sum(r["passed"] for r in uniform)}/8 pass | Active nonuniform: {sum(r["passed"] for r in active)}/3 pass',fontsize=12)
    for r,color in zip(active,('#247c88','#b45aa3','#d27b36')):
        h=histories[r['case_id']];t=np.arange(1,len(h)+1)/len(h);n=r['n']
        axs[0,0].plot(t,[a['marker_slip']/(.02/n) for a in h],color=color,label=f'N{n} markers')
        axs[0,0].plot(t,[a['probe_slip']/(.02/n) for a in h],'--',color=color,label=f'N{n} probes')
        axs[0,1].plot(t,[a['exterior_mass_relative_drift'] for a in h],color=color,label=f'N{n}')
    axs[0,0].axhline(.05,color='#777777',ls=':',label='Probe gate .05');axs[0,0].set(title='Enforced markers versus independent surface probes',xlabel='Time / test duration',ylabel='Slip / initial perturbation amplitude');axs[0,0].legend(fontsize=8,frameon=False,ncol=2)
    axs[0,1].axhline(1e-6,color='#777777',ls=':',label='Gate 1e-6');axs[0,1].set(title='Mass outside the sphere: geometric estimate',xlabel='Time / test duration',ylabel='Relative exterior mass drift');axs[0,1].legend(frameon=False)
    h=histories[disabled['case_id']];t=np.arange(1,len(h)+1)/len(h);enabled=next(r for r in active if r['n']==16);he=histories[enabled['case_id']]
    axs[1,0].plot(t,[a['marker_slip']/(.02/16) for a in h],label='Boundary disabled',color='#c35444');axs[1,0].plot(t,[a['marker_slip']/(.02/16) for a in he],label='Boundary enabled',color='#247c88');axs[1,0].set(title='Negative control detects an inactive interface',xlabel='Time / test duration',ylabel='Marker slip / initial amplitude');axs[1,0].legend(frameon=False)
    axs[1,1].axis('off');axs[1,1].text(0,1,'SCOPE OF THIS RESULT',weight='bold',va='top');axs[1,1].text(0,.87,'Complete collision + streaming + boundary impulse\nAll nodes stay active: no cover/uncover refill\nActual density used for exterior-mass estimate\n\nNot yet physical drag validation\nNot yet fibre transport or release fraction\nNo production promotion',va='top',linespacing=1.8)
    fig.text(.07,.04,'The active test has no analytical transient-drag comparator. Conservation and marker constraints alone do not validate transport.\nAll figures use immutable raw histories; no smoothing, rescaling or relaxed gates.',fontsize=10,color='#555555')
    fig.savefig(out/'full_ib_verification.png',dpi=180);plt.close(fig)
    dump(out/'render_manifest.json',{'source_hashes':{str(Path(__file__).resolve()):sha(__file__),str(RAW/'verification.json'):sha(RAW/'verification.json')},'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'decision':'integration_only_no_production'})
    print(table);print(out)

if __name__=='__main__':main()
