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

BASE=ROOT/'stage36_evaluations/stage36n_kinetic_20260908';RAW=BASE/'verification_01'
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')

def main():
    v=read(RAW/'verification.json');assert v['execution_completed'] and v['unit_tests_run']==151 and v['flow_conditions']==6;assert not (RAW/'failure.json').exists()
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
        from kinetic_shear_v1 import mode
        lam,vec,A=mode(r['tau'])
        spectral_error=max(abs(q['amplitude_normalized']-lam**(j+1)) for j,q in enumerate(h))
        assert spectral_error<1e-9
        close(h[0]['amplitude_normalized'],lam,1e-12);close(max(err),r['max_shear_amplitude_error'],1e-14)
        peak=int(np.argmax(err))+1;controls.append({'s':s,'max_error':max(err),'peak_step':peak,'first_step_measured':h[0]['amplitude_normalized'],'first_step_discrete_eigenvalue':lam,'max_discrete_mode_error':spectral_error,'passed':max(err)<=.02})
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
    comparisons={'time':[pair('s1_m56','s2_m56'),pair('s2_m56','s4_m56')]}
    gates={}
    for axis,ps in comparisons.items():
        gates[axis]={}
        for key in ('field_difference','impulse_history_difference','late_force_difference'):
            gates[axis][key]=ps[1][key]<=.02 and (ps[1][key]<ps[0][key] or max(ps[0][key],ps[1][key])<1e-12)
    qualified=all(all(g.values()) for g in gates.values()) and v['integration_gates_passed'] and v['shear_controls_passed']
    out=BASE/'render_01';out.mkdir(exist_ok=False)
    dump(out/'independent_audit.json',{'audit_passed':True,'cases':audit,'controls':controls,'comparisons':comparisons,'comparison_gates':gates,'refinement_qualified':qualified,'baseline_exact_stage36l_reproduction':False})

    oldbase=ROOT/'stage36_evaluations/stage36m_refinement_20260908'
    prior=read(oldbase/'render_01/independent_audit.json')
    report=f"""# Stage36N — kinetic initialization test

151 tests and six CPU runs completed. Saved first steps, quarter-state integrals and force ledgers independently reconstructed. All integration gates: {v['integration_gates_passed']}. Continuum shear controls: {v['shear_controls_passed']}. Time-scale refinement qualified: {qualified}.

Linear kinetic shear initialization preserves the initial density and velocity and selects the discrete transverse hydrodynamic eigenmode. It does not impose continuum decay during evolution. Maximum continuum normalized amplitude errors: {[c['max_error'] for c in controls]}. Maximum discrepancy from discrete eigenvalue powers: {[c['max_discrete_mode_error'] for c in controls]}.

Time comparisons (coarse then fine): {json.dumps(comparisons['time'],indent=2)}.

Gates: {json.dumps(gates)}. Same2% thresholds and improvement requirement as Stage36M. Force differences use distinct physical reference scales, not measured drag. Late-force window starts at t=.25. Fixed-grid time scaling changes relaxation and compressibility, so this is not a pure temporal order study.

The initialization corrects the isolated shear startup mode; it need not remove incompatibility between the initial shear and the moving no-slip sphere. No absolute permeability validation, physical drag, release fraction, migration or two-way coupling is qualified. Previous failed results remain untouched.

Next: isolate sphere-boundary startup using a bounded smooth forcing/ramp benchmark and an independent force comparator before any particle-release simulation.
"""
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    dump(out/'next_gate.json',{'evidence_manifest':str(RAW/'verification.json'),'evidence_sha256':sha(RAW/'verification.json'),'refinement_qualified':qualified,'production_execution_authorized':False,'release_prediction_qualified':False,'next_scope':'isolate boundary startup and verify candidate force against an independent comparator'})
    fig,ax=plt.subplots(1,2,figsize=(11,4.7));fig.subplots_adjust(top=.78,bottom=.22,wspace=.35)
    fig.suptitle('Stage36N | Kinetic initialization and force sensitivity',fontsize=16)
    x=np.arange(3);keys=['field_difference','impulse_history_difference','late_force_difference']
    for off,data,label,color in [(-.18,prior['comparisons']['time'][1],'Equilibrium start','#b45a55'),(.18,comparisons['time'][1],'Kinetic start','#267f91')]:
        ax[0].bar(x+off,[100*data[k] for k in keys],.36,label=label,color=color)
    ax[0].axhline(2,color='gray',ls=':');ax[0].set_xticks(x,['Velocity','Impulse','Late force']);ax[0].set_ylabel('Fine-pair difference (%)');ax[0].legend(frameon=False)
    ax[1].plot([1,2,4],[100*c['max_error'] for c in prior['controls']],'o-',label='Equilibrium start',color='#b45a55')
    ax[1].plot([1,2,4],[100*c['max_error'] for c in controls],'o-',label='Kinetic start',color='#267f91');ax[1].axhline(2,color='gray',ls=':');ax[1].set(xlabel='Time scaling factor',ylabel='Peak continuum shear error (%)');ax[1].legend(frameon=False)
    fig.text(.08,.06,'151 tests | 6 CPU runs | Fixed grid, unchanged viscosity and gates\nForce refinement and physical release remain separate verification questions.',fontsize=10)
    fig.savefig(out/'kinetic_comparison.png',dpi=170);plt.close(fig)
    dump(out/'render_manifest.json',{'source_hashes':{str(Path(__file__).resolve()):sha(__file__),str(RAW/'verification.json'):sha(RAW/'verification.json')},'artifact_hashes':{str(p):sha(p) for p in out.iterdir() if p.is_file()}})
    print(json.dumps({'controls':controls,'comparisons':comparisons,'gates':gates,'qualified':qualified},indent=2))

if __name__=='__main__':main()
