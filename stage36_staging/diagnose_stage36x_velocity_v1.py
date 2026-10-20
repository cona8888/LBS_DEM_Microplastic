"""Read-only flow diagnosis; derived files only. No new flow solves.

Contract: preserve Stage36W gates and comparator; quantify exterior mean-error
and zero-mean components, radial error, and complete momentum closure.
Decomposition is diagnostic, never a corrected acceptance measure.
"""
import json
from pathlib import Path
import numpy as np
import refined_ib_sphere_v1 as m
import verify_stage36q_nonzero_reference_v1 as ref
from verify_stage36r_manufactured_flow_v1 import ramp,gint
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

def main():
    raw=ROOT/'stage36_evaluations/stage36w_spatial_flow_20260908/verification_01'
    manifest=raw/'manifest.json';v=json.loads(manifest.read_text());assert v['completed'] and not (raw/'failure.json').exists()
    checked={str(manifest):sha(manifest)}
    for group in ('source_hashes','parent_hashes','artifact_hashes'):
        for p,h in v[group].items():assert sha(p)==h,p;checked[p]=h
    rows=[]
    for n in (12,16,24):
        x=(np.indices((n,n,n)).reshape(3,-1).T+.5)/n-.5;r=np.linalg.norm(x,axis=1);ext=r>ref.R;mask=(r>ref.R)&(r<ref.L)
        u0=ref.field(x);adv=np.zeros_like(x);lap=np.zeros_like(x);G,lap[mask]=ref.derivatives(x[mask]);adv[mask]=np.einsum('nij,nj->ni',G,u0[mask])
        h=json.loads((raw/f'n{n}_history.json').read_text());dt=1/n**2;integrated_source=np.zeros(3);history=[]
        # Analytical midpoint source sampled on the same frozen grid.
        for entry in h:
            g,gp=ramp(entry['time']-dt/2);source=gp*u0+g*g*adv-.1*g*lap
            integrated_source+=source.sum(axis=0)/n**3*dt
            history.append(integrated_source.copy())
        with np.load(raw/f'n{n}_states.npz') as z:
            initial=m.interior(z['initial'],np.ones(3)*n/2,n/5)[1]/n**2
            for q in range(1,5):
                f=z[f'quarter_{q}'];a=f.reshape(19,-1);rho=a.sum(axis=0);u=(m.C.T@a).T/rho[:,None]*n
                target=ramp(q/4)[0]*u0;err=u[ext]-target[ext];den=np.mean(np.sum(u0[ext]**2,axis=1));mean=err.mean(axis=0);mse=np.mean(np.sum(err**2,axis=1));centered=np.mean(np.sum((err-mean)**2,axis=1))
                assert abs(mse-centered-mean@mean)<1e-18
                k=q*n*n//4;inside=m.interior(f,np.ones(3)*n/2,n/5)[1]/n**2
                total=(m.C.T@a).sum(axis=1)/n**2
                # Whole-step force ledger: P_ext = integrated(source - inside_source - body_force).
                ledger=history[k-1]-dt*np.sum([np.array(e['force'])+np.array(e['interior_source_force']) for e in h[:k]],axis=0)
                residual=total-inside+initial-ledger
                assert np.max(abs(residual))<1e-10
                radial={}
                for name,sel in [('near',(r>.2)&(r<.3)),('annulus_outer',(r>=.3)&(r<.4)),('outside_support',r>=.4)]:
                    radial[name]=float(np.sqrt(np.mean(np.sum((u[sel]-target[sel])**2,axis=1))/den))
                rows.append({'n':n,'time':q/4,'rms_error':float(np.sqrt(mse/den)),'mean_error':mean.tolist(),'mean_fraction_squared_error':float(mean@mean/mse),'zero_mean_rms_error':float(np.sqrt(centered/den)),'radial_errors':radial,'exterior_momentum':(total-inside).tolist(),'momentum_closure_residual':residual.tolist()})
    out=ROOT/'stage36_evaluations/stage36x_velocity_diagnosis_20260909/analysis_01';out.mkdir(parents=True,exist_ok=False)
    (out/'diagnostics.json').write_text(json.dumps(rows,indent=2))
    lines=['# Stage36X — saved-field velocity diagnosis','', 'No new flow solves. Parent hashes and the exterior momentum ledger were checked. Original 2% failures remain unchanged.','', '| Grid | Final RMS error | Mean component of squared error | Zero-mean RMS error |','|---|---:|---:|---:|']
    for row in rows:
        if row['time']==1:lines.append(f"| {row['n']} | {row['rms_error']:.2%} | {row['mean_fraction_squared_error']:.2%} | {row['zero_mean_rms_error']:.2%} |")
    lines+=['','Mean removal is a diagnostic decomposition, not an allowed correction. A closed momentum ledger does not imply a correct velocity field. Inspect the regional errors before assigning the discrepancy to interface leakage alone.','', 'Next bounded check: independently test manufactured source derivatives and the discrete first-step forcing/collision/streaming identity, then isolate forcing on a smooth periodic field without an interface. Do not modify viscosity, reference or gates to fit these results.']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    (out/'manifest.json').write_text(json.dumps({'completed':True,'new_flow_solves':0,'source_hash':sha(__file__),'parent_hashes':checked,'artifact_hashes':{str(p):sha(p) for p in out.iterdir()},'release_qualified':False},indent=2))
    print('\n'.join(lines))
if __name__=='__main__':main()
