"""Independent saved-artifact audit; no flow run and no edits to evidence."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
from body_link_extractor_v1 import C,OPP

BASE=ROOT/'stage36_evaluations/stage36j_moving_sphere_20260908'
RAW=BASE/'verification_01'
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def close(a,b,tol=1e-10):np.testing.assert_allclose(a,b,rtol=0,atol=tol)

def main():
    v=read(RAW/'verification.json');assert v['execution_completed'] and v['unit_tests_passed'] and v['flow_conditions']==8
    assert not (RAW/'failure.json').exists()
    hashes={}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for p,h in v[group].items():assert sha(p)==h,p;hashes[p]=h
    selected=read(ROOT/'stage36_evaluations/stage36i_timelevel_20260908/render_02/selected_implementation.json')
    assert selected['required_explicit_argument']=={'incoming_level':'post'}
    assert sha(selected['selected_source'])==selected['selected_source_sha256']
    histories={};audits=[];rows=v['cases']
    assert [(r['n'],r['direction'],r['phase_lu']) for r in rows]==[(n,d,0.) for n in (12,16,24) for d in (1,-1)]+[(16,0,0.),(16,1,.5)]
    for r in rows:
        name=r['case_id'];n=r['n'];M=r['initial_mass'];U=np.array(r['velocity_lu']);h=read(RAW/(name+'_history.json'));histories[name]=h
        assert len(h)==n*n and r==read(RAW/(name+'_result.json'))
        x=np.array(list(np.ndindex(n,n,n)),float)+.5
        with np.load(RAW/(name+'_states.npz')) as z:
            for stage in ('initial','final'):
                centre=z['centre_'+stage];f=z[stage].reshape(19,-1);a=np.linalg.norm(x-centre,axis=1)>n/5
                assert np.all(f[:,a]>0) and np.isfinite(f).all() and np.all(f[:,~a]==0)
                close(f[:,a].sum(axis=0),1);close((C.T@f[:,a])/f[:,a].sum(axis=0),np.tile(U[:,None],(1,a.sum())))
                close(f.sum(),M if stage=='initial' else h[-1]['mass_after'])
            close(z['centre_final']-z['centre_initial'],n*n*U)
        maxmass=maxmom=maxvol=maxforce=maxboundary=0.
        for t,row in enumerate(h):
            assert row['step']==t+1
            close(np.array(row['centre_after'])-row['centre_before'],U)
            nb=int(np.sum(np.linalg.norm(x-row['centre_before'],axis=1)>n/5));na=int(np.sum(np.linalg.norm(x-row['centre_after'],axis=1)>n/5))
            assert nb==row['fluid_nodes_before'] and na==row['fluid_nodes_after']
            dm=row['mass_after']-row['mass_before'];dp=np.array(row['momentum_after'])-row['momentum_before']
            mr=dm-row['collision_mass']-row['boundary_mass']-row['status_mass']
            pr=dp-row['collision_momentum']+np.array(row['boundary_impulse'])+row['status_impulse']
            close(mr,row['mass_ledger_residual']);close(pr,row['momentum_ledger_residual'])
            close(row['traction_candidate'],np.array(row['boundary_impulse'])+row['status_impulse'])
            if t:
                close(row['mass_before'],h[t-1]['mass_after']);close(row['momentum_before'],h[t-1]['momentum_after'])
            maxmass=max(maxmass,abs(row['mass_after']-M)/M);maxmom=max(maxmom,float(np.max(np.abs(pr)))/M)
            maxvol=max(maxvol,abs(row['mass_after']-M-(na-r['initial_fluid_nodes']))/M)
            maxforce=max(maxforce,float(np.max(np.abs(row['traction_candidate']))));maxboundary=max(maxboundary,float(np.max(np.abs(row['boundary_impulse']))))
        close(maxmass,r['max_mass_relative_drift'],1e-15);close(maxvol,r['max_binary_volume_residual_relative'],1e-15);close(maxforce,r['max_traction_candidate'],1e-15)
        transition_checked=False
        if r['direction']:
            with np.load(RAW/(name+'_transition.npz')) as z:
                a=np.linalg.norm(x-z['centre'],axis=1)>n/5;b=np.linalg.norm(x-z['centre']-U,axis=1)>n/5
                added=np.flatnonzero(b&~a);removed=np.flatnonzero(a&~b);ret=a&b
                np.testing.assert_array_equal(added,z['added_indices']);np.testing.assert_array_equal(removed,z['removed_indices'])
                old=z['old'].reshape(19,-1);new=z['new'].reshape(19,-1);inter=z['intermediate'].reshape(19,-1)
                close(new[:,ret],inter[:,ret]);assert np.all(new[:,~b]==0)
                # Independently enumerate every eligible two-point ray, then reconstruct refill.
                stencil=set()
                for j in added:
                    point=np.array(np.unravel_index(j,(n,n,n)));vals=[]
                    for c in C[1:]:
                        j1=np.ravel_multi_index(tuple((point+c)%n),(n,n,n));j2=np.ravel_multi_index(tuple((point+2*c)%n),(n,n,n))
                        if ret[j1] and ret[j2]:stencil.add((int(j),int(j1),int(j2)));vals.append(2*inter[:,j1]-inter[:,j2])
                    assert vals;close(new[:,j],np.mean(vals,axis=0))
                assert stencil=={tuple(v) for v in z['refill_stencils'].tolist()}
                # Explicit polynomial collision, scalar link checks and full streaming reconstruction.
                rho=old[:,a].sum(axis=0);u=C.T@old[:,a]/rho;cu=C@u;weights=np.array([1/3]+[1/18]*6+[1/36]*12)
                post=np.zeros_like(old);post[:,a]=old[:,a]-(old[:,a]-weights[:,None]*rho*(1+3*cu+4.5*cu**2-1.5*np.sum(u*u,axis=0)))/.8
                reconstructed=np.zeros_like(old)
                for k,c in enumerate(C):
                    for j in np.flatnonzero(a):
                        point=np.array(np.unravel_index(j,(n,n,n)));src=np.ravel_multi_index(tuple((point-c)%n),(n,n,n));reconstructed[k,j]=post[k,src]
                seen=set()
                for k,j,q,outgoing,incoming in z['links']:
                    k=int(k);j=int(j);seen.add((k,j));c=C[k];point=np.array(np.unravel_index(j,(n,n,n)))
                    src=np.ravel_multi_index(tuple((point-c)%n),(n,n,n));assert a[j] and not a[src]
                    close(np.linalg.norm(x[j]-q*c-z['centre']),n/5);assert 0<q<=1
                    far=np.ravel_multi_index(tuple((point+c)%n),(n,n,n));B=6*weights[k]*float(c@U)
                    expected=(2*q*post[OPP[k],j]+(1-2*q)*post[OPP[k],far]+B) if q<=.5 else ((post[OPP[k],j]+B)+(2*q-1)*post[k,j])/(2*q)
                    close(outgoing,post[OPP[k],j]);close(incoming,expected);reconstructed[k,j]=expected
                close(reconstructed,inter)
                row=h[int(z['step'])-1];close(new.sum(),row['mass_after']);close(old.sum(),row['mass_before'])
                close(C.T@(inter[:,removed].sum(axis=1)-new[:,added].sum(axis=1)),row['status_impulse'])
                transition_checked=True
        audits.append({'case_id':name,'state_history_geometry_ledgers_checked':True,'transition_independently_reconstructed':transition_checked,'max_mass_drift':maxmass,'max_volume_residual':maxvol,'max_boundary_impulse':maxboundary,'max_force_candidate':maxforce})
    out=BASE/'render_02';out.mkdir(exist_ok=False)
    dump(out/'independent_audit.json',{'audit_passed':True,'physical_qualification_passed':False,'checked_hashes':hashes,'cases':audits})
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(2,2,figsize=(12,9));fig.subplots_adjust(top=.83,bottom=.17,hspace=.52,wspace=.3)
    fig.suptitle('Stage36J | A moving sphere exposes the next failure',fontsize=19,x=.07,ha='left',y=.96)
    fig.text(.07,.895,'121 unit tests pass. All 8 CPU cases preserve uniform flow; 7 moving cases fail mass and force gates.',fontsize=11)
    for n,color in zip((12,16,24),('#1b9e77','#3978bb','#b45aa3')):
        h=histories[f'N{n}_d1_phase0'];axs[0,0].plot(np.arange(1,n*n+1)/(n*n),[(v['mass_after']-h[0]['mass_before'])/h[0]['mass_before']*100 for v in h],label=f'N={n}',color=color)
    axs[0,0].set(title='Actual mass changes despite constant sphere volume',xlabel='Physical time / test duration',ylabel='Signed fluid mass change (%)');axs[0,0].legend(frameon=False)
    h=histories['N16_d1_phase0'];t=np.arange(1,257)/256;delta=np.array([v['mass_after']-h[0]['mass_before'] for v in h]);nodes=np.array([v['fluid_nodes_after']-h[0]['fluid_nodes_before'] for v in h])
    axs[0,1].plot(t,delta,label='Measured mass change',lw=2);axs[0,1].plot(t,nodes,'--',label='Fluid-node count change',color='orange');axs[0,1].set(title='The mass defect follows voxel-count changes (N16)',xlabel='Physical time / test duration',ylabel='Mass change (lattice units)');axs[0,1].legend(frameon=False)
    axs[1,0].plot(t,[v['traction_candidate'][0] for v in h],label='Boundary + status candidate',color='#d05943');axs[1,0].plot(t,[v['boundary_impulse'][0] for v in h],label='Boundary only',color='#3978bb');axs[1,0].set(title='Bookkeeping is not physical force (N16)',xlabel='Physical time / test duration',ylabel='x impulse per step (lattice units)');axs[1,0].legend(frameon=False,fontsize=9)
    axs[1,1].axis('off')
    lines=['PREDECLARED GATES','Uniform density & velocity: 8 / 8 pass','Mass & momentum ledgers: 8 / 8 pass','Actual global mass: 1 / 8 pass','Zero-force candidate: 1 / 8 pass','','Stationary control passes; all moving cases fail.','No thresholds changed. No production promotion.']
    axs[1,1].text(0,1,'\n'.join(lines),va='top',linespacing=1.65,fontsize=11)
    fig.text(.07,.035,'Scope: prescribed rigid sphere + co-moving uniform fluid; zero relative-flow Reynolds number.\nNot drag validation, fibre transport, contamination release, or two-way coupling.',fontsize=10,color='#555555')
    fig.savefig(out/'sphere_verification.png',dpi=180);plt.close(fig)
    table='\n'.join(f"| {r['case_id']} | {100*r['max_mass_relative_drift']:.5f}% | {r['max_boundary_impulse']:.3e} | {r['max_traction_candidate']:.5f} |" for r in rows)
    report=f'''# Stage36J — complete moving-sphere verification

Decision: **do not promote** this binary-mask/refill/force combination. All eight CPU runs completed; {v['unit_tests_run']} unit tests passed. Seven translating cases fail the frozen global-mass and zero-force-candidate gates; the stationary control passes. This is a numerical falsification result, not a physical release result.

| Case | Max relative mass drift | Max boundary-only impulse (LU) | Max boundary + status candidate (LU) |
|---|---:|---:|---:|
{table}

The exact continuum solution is uniform co-moving fluid and zero net force. All cases preserve density and velocity to the frozen 1e-10 tolerances. Numerical mass and momentum ledgers close, but that does not imply mass conservation or a physical force estimate. Actual mass follows changing binary fluid-node count; the maximum residual after subtracting that diagnostic is {max(r['max_binary_volume_residual_relative'] for r in rows):.3e} of initial mass. The maximum density and velocity errors are {max(r['max_density_error'] for r in rows):.3e} and {max(r['max_velocity_error'] for r in rows):.3e}, respectively.

The ledger-closed boundary-plus-status impulse has nonzero spikes even in uniform co-motion. Boundary-only impulse remains near roundoff in this test; that alone does not qualify a general hydrodynamic force formulation. The new evaluator independently checked frozen hashes, all eight saved initial/final states, every-step geometry/ledgers, and all seven archived topology-change steps, reconstructing collision, streaming, boundary interpolation and refill. Intermediate full states are saved only for those seven transitions; other time steps are audited through histories and endpoint states.

No monotonic convergence claim is made for binary-volume errors. No density clipping, mass rescaling, gate relaxation, GPU/production run or change to prior evidence was used. Angular momentum is not globally qualified by this periodic benchmark.

## Next bounded gate

Select and document a volume-consistent moving-boundary representation and a justified hydrodynamic-force formulation. First test geometric swept volume and uniform co-motion conservation, then nonzero-relative-flow sphere drag, before any fibre release pilot. Do not simply convert covered/exposed population bookkeeping into physical body force or rescale density to hide the defect. No production or release execution is authorized by this report.

Primary context: [Peng et al. (2016), DOI 10.1016/j.camwa.2015.08.027](https://research.me.udel.edu/lwang/reprints/Peng_etal_CAMWA_2016.pdf). This benchmark is not a replication or validation of their solver.
'''
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    dump(out/'next_gate.json',{'decision':'blocked_binary_volume_and_force_candidate','next_scope':'volume-consistent representation and force formulation design, then bounded CPU verification','production_execution_authorized':False,'release_prediction_qualified':False})
    dump(out/'render_manifest.json',{'source_hashes':{str(RAW/'verification.json'):sha(RAW/'verification.json'),str(Path(__file__).resolve()):sha(__file__)},'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'decision':'fail_closed'})
    print(json.dumps(audits,indent=2));print(out)

if __name__=='__main__':main()
