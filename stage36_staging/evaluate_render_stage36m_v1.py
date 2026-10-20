"""Independent scaling, saved-step audit and paired refinement comparison."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from verify_stage36d_wrench_transfer_v1 import ROOT,sha
from evaluate_render_stage36l_v1 import eq,kernel,integral,close
from body_link_extractor_v1 import C

BASE=ROOT/'stage36_evaluations/stage36m_refinement_20260908';RAW=BASE/'verification_01'
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')

def main():
    v=read(RAW/'verification.json');assert v['execution_completed'] and v['unit_tests_run']==147 and v['flow_conditions']==8;assert not (RAW/'failure.json').exists()
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for p,h in v[group].items():assert sha(p)==h,p
    rows={r['case_id']:r for r in v['cases']};H={};fields={};audit=[]
    for name,r in rows.items():
        s=r['s'];h=read(RAW/(name+'_history.json'));H[name]=h;assert len(h)==256*s
        dt=1/(256*s);dx=1/16;close((r['tau']-.5)/3*dx*dx/dt,.1,1e-15);assert r['force_scale']==s*s and r['velocity_scale']==16*s
        with np.load(RAW/(name+'_states.npz')) as z:
            fields[name]=[]
            for k in range(1,5):
                f=z[f'quarter_{k}'];assert np.isfinite(f).all() and np.all(f>0);a=f.reshape(19,-1);u=(C.T@a).T/a.sum(axis=0)[:,None]*dx/dt;fields[name].append(u)
                row=h[k*64*s-1];inside=integral(f,np.array(row['centre_after']),3.2);close(inside[0],row['interior_mass_after']);close(inside[1:],row['interior_momentum_after']);close(f.sum(),row['mass_after'])
            fine=integral(z['quarter_4'],z['centre_final'],3.2,True)[0];close(abs(fine-h[-1]['interior_mass_after'])/h[0]['exterior_mass_before'],r['fine_quadrature_discrepancy'],1e-12)
            if name=='s1_m56':
                with np.load(ROOT/'stage36_evaluations/stage36l_full_ib_sphere_20260908/verification_01/N16_d1_phase0_p1_ib1_states.npz') as old:
                    np.testing.assert_array_equal(z['initial'],old['initial']);np.testing.assert_array_equal(z['quarter_4'],old['final'])
        for t,a in enumerate(h):
            close(a['time'],(t+1)*dt,1e-15);close(a['force_physical'],np.array(a['force_candidate'])*dx**4/dt**2,1e-12)
            dp=np.array(a['momentum_after'])-a['momentum_before'];di=np.array(a['interior_momentum_after'])-a['interior_momentum_before'];I=np.array(a['force_on_fluid'])
            close(a['force_candidate'],-I+di);close(a['momentum_ledger_residual'],dp-I)
            close(a['exterior_mass_after'],a['mass_after']-a['interior_mass_after'])
            if t:close(a['mass_before'],h[t-1]['mass_after']);close(a['momentum_before'],h[t-1]['momentum_after'])
        with np.load(RAW/(name+'_firststep.npz')) as z:
            f=z['old'];a=f.reshape(19,-1);rho=a.sum(axis=0);post=(a-(a-eq(rho,C.T@a/rho))/r['tau']).reshape(f.shape);expected=np.empty_like(f)
            for k in range(19):
                idx=(np.indices((16,16,16))-C[k,:,None,None,None])%16;expected[k]=post[k][tuple(idx)]
            close(expected,z['streamed'],1e-14);g=np.array(list(np.ndindex(16,16,16)),float)+.5;J=np.ones((r['markers'],4096))
            for d in range(3):J*=kernel(g[None,:,d]-z['markers'][:,None,d])
            a=z['streamed'].reshape(19,-1);rho=a.sum(axis=0);u=(C.T@a).T/rho[:,None];lam=z['marker_impulses'];imp=J.T@lam
            close(imp,z['grid_impulse'],1e-12);close((J/rho)@J.T@lam,z['velocity']-J@u,1e-12)
            close(a+eq(rho,(u+imp/rho[:,None]).T)-eq(rho,u.T),z['new'].reshape(19,-1),1e-13)
        audit.append({'case_id':name,'physical_scaling_checked':True,'all_quarter_states_integrals_checked':True,'first_step_reconstructed':True})
    controls=[];first_exact=(2+np.cos(2*np.pi/16))/3
    for r in v['controls']:
        h=read(RAW/(r['case_id']+'_history.json'));s=r['s'];assert len(h)==256*s
        err=[]
        for j,a in enumerate(h):
            exact=float(np.exp(-.1*(2*np.pi)**2*(j+1)/(256*s)));close(a['exact'],exact,1e-15);err.append(abs(a['amplitude_normalized']-exact))
        close(h[0]['amplitude_normalized'],first_exact,1e-13);close(max(err),r['max_shear_amplitude_error'],1e-14)
        peak=int(np.argmax(err))+1;controls.append({'s':s,'max_error':max(err),'peak_step':peak,'first_step_measured':h[0]['amplitude_normalized'],'first_step_analytical_lattice_value':float(first_exact),'passed':max(err)<=.02})
    V=4*np.pi*.2**3/3;Jscale=V*.02;Fscale=6*np.pi*.1*.2*.02
    averaged={};cum={}
    for name,r in rows.items():
        s=r['s'];f=np.array([a['force_candidate'] for a in H[name]])*s*s
        averaged[name]=f.reshape(256,s,3).mean(axis=1)
        cum[name]=np.cumsum(np.array([a['force_candidate'] for a in H[name]])*s/256,axis=0)[s-1::s]
        close(np.sum(averaged[name],axis=0)/256,cum[name][-1],1e-12)
    def pair(a,b):
        field=max(float(np.sqrt(np.mean(np.sum((x-y)**2,axis=1))))/.02 for x,y in zip(fields[a],fields[b]))
        impulse=float(np.max(np.linalg.norm(cum[a]-cum[b],axis=1)))/Jscale
        # Index63 ends at t=.25; include this and subsequent common intervals.
        force=float(np.sqrt(np.mean(np.sum((averaged[a][63:]-averaged[b][63:])**2,axis=1))))/Fscale
        return {'coarse':a,'fine':b,'field_difference':field,'impulse_history_difference':impulse,'late_force_difference':force}
    comparisons={'time':[pair('s1_m56','s2_m56'),pair('s2_m56','s4_m56')],'markers':[pair('s1_m32','s1_m56'),pair('s1_m56','s1_m80')]}
    gates={}
    for axis,ps in comparisons.items():
        gates[axis]={}
        for key in ('field_difference','impulse_history_difference','late_force_difference'):
            gates[axis][key]=ps[1][key]<=.02 and (ps[1][key]<ps[0][key] or max(ps[0][key],ps[1][key])<1e-12)
    qualified=all(all(g.values()) for g in gates.values()) and v['integration_gates_passed'] and v['shear_controls_passed']
    out=BASE/'render_01';out.mkdir(exist_ok=False)
    dump(out/'independent_audit.json',{'audit_passed':True,'cases':audit,'controls':controls,'comparisons':comparisons,'comparison_gates':gates,'refinement_qualified':qualified,'baseline_exact_stage36l_reproduction':True})
    table='\n'.join(f"| {axis} | {p['coarse']} -> {p['fine']} | {100*p['field_difference']:.3f}% | {100*p['impulse_history_difference']:.3f}% | {100*p['late_force_difference']:.3f}% |" for axis,ps in comparisons.items() for p in ps)
    case_table='\n'.join(f"| {name} | {r['tau']} | {100*r['max_probe_slip_normalized']:.3f}% | {r['max_exterior_mass_drift']:.3e} | {r['max_condition_number']:.3e} | {', '.join(k for k,b in r['gates'].items() if not b) or 'none'} |" for name,r in rows.items())
    report=f'''# Stage36M — time-scale and surface-marker sensitivity

**Refinement qualified: {qualified}.** 147 unit tests and the saved-evidence audit passed. Eight CPU runs completed: five unique immersed cases and three unforced shear controls. The shared s1,m56 baseline reproduces Stage36L initial and final fields exactly. This is not physical drag validation.

## Separate refinement comparisons

| Axis | Pair | Quarter-field difference | Integrated-force-history difference | Late force-history difference |
|---|---|---:|---:|---:|
{table}

Each fine pair must be <=2% and improve on its coarse pair. Velocity differences are RMS vector errors normalized by perturbation amplitude .02. Impulses are normalized by rho*V*.02. Force differences use RMS vector differences of common-dt averages over endpoints t>=.25, scaled by 6*pi*nu*R*.02; this scale is not a drag-validation comparator. All fine-step impulses contribute to the interval averages. Time and marker refinements were varied separately, not as a factorial campaign.

Comparison gate decisions: {json.dumps(gates)}.

| Case | tau | Max common-probe slip / amplitude | Exterior-mass estimate drift | Max condition number | Failed integration gates |
|---|---:|---:|---:|---:|---|
{case_table}

## Shear-control failure and analytical diagnosis

The maximum normalized sine-amplitude errors are {100*controls[0]['max_error']:.4f}%, {100*controls[1]['max_error']:.4f}%, and {100*controls[2]['max_error']:.4f}% at s=1,2,4. Peak errors occur at steps {[r['peak_step'] for r in controls]}. The s4 control exceeds the predeclared 2% gate.

All controls start with local equilibrium populations. At their first step collision leaves that equilibrium unchanged; D3Q19 streaming reduces the transverse sine-mode momentum amplitude by (2+cos(2*pi/N))/3 = {first_exact:.12f}, independent of tau. The continuum first-step factor approaches1 as dt decreases. This identity matches each saved first step to floating-point precision and explains the observed initial-step discrepancy without a new fit. It identifies a kinetic initialization effect at fixed N, not proof that changing physical viscosity would fix it. No initialization was retuned in this stage.

At fixed N, time scaling also changes relaxation and numerical compressibility. Therefore these comparisons cannot establish a pure temporal convergence order. The full scheme's force and boundary-location accuracy still require independent evidence. Uniform-flow conservation and enforced-marker slip are insufficient.

## Next bounded gate

Fail closed before sphere-drag or fibre-release claims. Derive and verify a shear-mode initialization consistent with the discrete kinetic dynamics, compare it with the preserved equilibrium-start control, and establish which force-history discrepancies are startup-related versus persistent discretization error. Also retain a common off-marker probe cloud when studying marker density. Do not increase thresholds, use pinv/regularization, or tune physical viscosity to conceal numerical error. Any follow-on corrected runs require new immutable evidence.

Reproduction: stage36_staging/verify_stage36m_refinement_v1.py; analysis stage36_staging/evaluate_render_stage36m_v1.py. Python3.12 with BLASthreads1. Existing output directories are refused. Every dependency and parent artifact is hash-bound in verification_01/verification.json. All quarter-time states and the first-step packet were independently audited; other steps are checked through immutable histories. No GPU/production or new microplastic physics was run.
'''
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    dump(out/'next_gate.json',{'evidence_manifest':str(RAW/'verification.json'),'evidence_sha256':sha(RAW/'verification.json'),'refinement_qualified':qualified,'comparison_gates':gates,'next_scope':'derive and verify discrete shear-mode initialization; separate startup and persistent force sensitivity; common-probe marker checks','production_execution_authorized':False,'release_prediction_qualified':False})
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False});fig,axs=plt.subplots(2,2,figsize=(12,9));fig.subplots_adjust(top=.83,bottom=.16,hspace=.52,wspace=.34)
    fig.suptitle('Stage36M | Passing integration tests does not establish refinement',fontsize=18,y=.96)
    fig.text(.07,.9,'147 tests passed | 8 CPU runs completed | Baseline exactly reproduced | Refinement not qualified',fontsize=12)
    t=np.arange(1,257)/256
    for name,color in zip(('s1_m56','s2_m56','s4_m56'),('#247c88','#b45aa3','#d27b36')):axs[0,0].plot(t[63:],averaged[name][63:,0]/Fscale,label=name,color=color)
    axs[0,0].set(title='Time-scale sensitivity of candidate force',xlabel='Physical time',ylabel='Interval-averaged x force / reference scale');axs[0,0].legend(frameon=False)
    keys=('field_difference','impulse_history_difference','late_force_difference');x=np.arange(3)
    for shift,axis,color in ((-.18,'time','#247c88'),(.18,'markers','#b45aa3')):axs[0,1].bar(x+shift,[100*comparisons[axis][1][k] for k in keys],.36,label=axis,color=color)
    axs[0,1].axhline(2,color='#666666',ls=':',label='Fine-pair gate2%');axs[0,1].set_xticks(x,['Velocity\nfields','Integrated\nforce','Late force\nhistory']);axs[0,1].set(title='Fine-pair differences (different reference scales)',ylabel='Normalized difference (%)');axs[0,1].legend(frameon=False,fontsize=9)
    axs[1,0].plot([1,2,4],[100*c['max_error'] for c in controls],'o-',color='#c35444');axs[1,0].axhline(2,ls=':',color='#666666');axs[1,0].set_xticks([1,2,4]);axs[1,0].set(title='Equilibrium-start shear control: error grows',xlabel='Time refinement factor s',ylabel='Peak sine-amplitude error (%)')
    axs[1,1].axis('off');axs[1,1].text(0,1,'IDENTIFIED LIMITATIONS',weight='bold',va='top');axs[1,1].text(0,.85,'Sparse32-marker boundary fails probe-slip gate.\nFinest-time shear control fails its 2% gate.\nFirst streaming step explains shear startup error.\n\nDo not claim time convergence or validated drag.\nNext: discrete kinetic initialization + force diagnosis.\nFibre-release predictions remain unqualified.',va='top',linespacing=1.8)
    fig.text(.07,.04,'Fixed-grid time scaling also changes relaxation and numerical compressibility. Force is an accounting candidate, not validated traction.\nAll failed gates are preserved; no parameter tuning, new production run or release claim.',fontsize=10,color='#555555');fig.savefig(out/'refinement_verification.png',dpi=180);plt.close(fig)
    dump(out/'render_manifest.json',{'source_hashes':{str(Path(__file__).resolve()):sha(__file__),str(RAW/'verification.json'):sha(RAW/'verification.json'),str(ROOT/'stage36_staging/evaluate_render_stage36l_v1.py'):sha(ROOT/'stage36_staging/evaluate_render_stage36l_v1.py')},'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()},'decision':'refinement_fail_closed'})
    print(json.dumps({'comparisons':comparisons,'gates':gates,'controls':controls},indent=2));print(out)

if __name__=='__main__':main()
