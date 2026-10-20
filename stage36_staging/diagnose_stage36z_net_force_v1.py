"""Saved-run diagnostic, not a solver correction. Signed impulse decomposition.
P_ext = (I_source-I_exact) - I_inside + (I_exact-I_body).
Continuum manufactured exterior momentum is zero. All terms normalized by
F_final * integral(g,0,1). Retain original acceptance failures; no new flows.
"""
import json
import numpy as np
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
from verify_stage36r_manufactured_flow_v1 import ramp,gint
import verify_stage36q_nonzero_reference_v1 as ref
import refined_ib_sphere_v1 as m

def main():
    raw=ROOT/'stage36_evaluations/stage36w_spatial_flow_20260908/verification_01'
    p=raw/'manifest.json';v=json.loads(p.read_text());assert v['completed'] and not (raw/'failure.json').exists();checked={str(p):sha(p)}
    for group in ('source_hashes','parent_hashes','artifact_hashes'):
        for f,h in v[group].items():assert sha(f)==h;checked[f]=h
    rows=[];F0=4*np.pi/3*.1*.2**3*2*.01/.2**2;Iref=F0*gint(1)
    for n in (12,16,24):
        dt=1/n**2;x=(np.indices((n,n,n)).reshape(3,-1).T+.5)/n-.5;r=np.linalg.norm(x,axis=1);mask=(r>.2)&(r<.4);u=ref.field(x)
        adv=np.zeros_like(x);lap=np.zeros_like(x);G,lap[mask]=ref.derivatives(x[mask]);adv[mask]=np.einsum('nij,nj->ni',G,u[mask]);Is=np.zeros(3)
        h=json.loads((raw/f'n{n}_history.json').read_text())
        for e in h:
            g,gp=ramp(e['time']-dt/2);Is+=(gp*u+g*g*adv-.1*g*lap).sum(axis=0)*dt/n**3
        Ib=dt*np.sum([e['force'] for e in h],axis=0);Ii=dt*np.sum([e['interior_source_force'] for e in h],axis=0);exact=np.array([Iref,0,0])
        with np.load(raw/f'n{n}_states.npz') as z:
            f=z['quarter_4'];a=f.reshape(19,-1);Pe=((m.C.T@a).sum(axis=1)-m.interior(f,np.ones(3)*n/2,n/5)[1])/n**2
        terms=np.array([Is-exact,-Ii,exact-Ib]);res=Pe-terms.sum(axis=0);assert np.max(abs(res))<1e-10
        rows.append({'n':n,'signed_source_error':terms[0].tolist(),'signed_interior_correction':terms[1].tolist(),'signed_body_deficit':terms[2].tolist(),'normalized_x_terms':(terms[:,0]/Iref).tolist(),'exterior_momentum':Pe.tolist(),'normalized_exterior_x':float(Pe[0]/Iref),'closure':res.tolist()})
    out=ROOT/'stage36_evaluations/stage36z_net_force_20260909/analysis_01';out.mkdir(parents=True,exist_ok=False)
    (out/'decomposition.json').write_text(json.dumps(rows,indent=2))
    lines=['# Stage36Z — signed net-force decomposition','', 'No new simulations or changes to force definitions. Percentages use the analytical body impulse, not velocity RMS.','', '| Grid | Source error | Interior correction | Body-force deficit | Net exterior momentum |','|---|---:|---:|---:|---:|']
    for r in rows:
        a,b,c=r['normalized_x_terms'];lines.append(f"| {r['n']} | {a:+.2%} | {b:+.2%} | {c:+.2%} | {r['normalized_exterior_x']:+.2%} |")
    lines+=['','The three signed terms reproduce saved exterior momentum to absolute tolerance 1e-10. This is an accounting decomposition, not independent causal identification: body force already contains the interior-source subtraction. Changing that subtraction alone changes reported force, not the stored velocity or momentum.','', 'Do not subtract mean velocity, tune force to the analytical value, or remove an actual injected source from the ledger. Next useful intervention is a separately versioned, bounded source-discretization comparison on the same sphere and reference, with unchanged gates; a saved-data ledger cannot establish the outcome of that intervention. Release/drag qualification remains withheld.']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8');(out/'manifest.json').write_text(json.dumps({'completed':True,'new_flow_solves':0,'source_hash':sha(__file__),'parent_hashes':checked,'artifact_hashes':{str(f):sha(f) for f in out.iterdir()}},indent=2));print('\n'.join(lines))
if __name__=='__main__':main()
