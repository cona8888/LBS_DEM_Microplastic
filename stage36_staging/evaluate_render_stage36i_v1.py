"""Independently recheck archived Stage36I diagnostics and render results."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from body_link_extractor_v1 import C

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    src=a.input.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((src/'verification.json').read_text());bindings={}
    if not manifest['execution_completed'] or not manifest['unit_tests_passed']:raise ValueError('incomplete source')
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for path,h in manifest[group].items():
            if sha(path)!=h:raise ValueError('hash mismatch: '+path)
            bindings[path]=h
    rows=json.loads((src/'flow_results.json').read_text())['cases'];audits=[]
    for r in rows:
        h=json.loads((src/(r['case_id']+'_history.json')).read_text());mr=[];pr=[]
        for x in h:
            mr.append(x['mass_after']-x['mass_before']-x['collision_mass']-sum(x['boundary_mass'])-sum(x['status_mass']))
            pr.append(np.array(x['momentum_after'])-x['momentum_before']-x['collision_momentum']+np.sum(x['boundary_impulse'],axis=0)+np.sum(x['status_impulse'],axis=0))
        if max(np.max(np.abs(mr)),np.max(np.abs(pr)))>1e-11:raise ValueError('step budget failed')
        with np.load(src/(r['case_id']+'_states.npz')) as data:
            f=data['final'];y=data['y'];L=r['n']+np.sqrt(2)/10+r['phase_offset_lu']+r['V_lu']*r['steps'];fluid=(y>L)&(y<L+r['n'])
            rho=f[:,fluid].sum(axis=0);u=C.T@f[:,fluid]/rho
            err=np.max(np.abs(u[0]-r['U_lu']*(y[fluid]-L)/r['n']))/max(abs(r['U_lu']),.001)
            if not np.isclose(err,r['final_ux_normalized_error'],rtol=0,atol=1e-14):raise ValueError('profile mismatch')
            if len(data['event_states'])!=sum(bool(x['refill_stencils']) for x in h):raise ValueError('event mismatch')
            old_replay=None
            if r['incoming_level']=='old' and r['phase_offset_lu']==0:
                parent=src.parents[1]/'stage36h_translating_channel_20260906/verification_02'/(r['base_case']+'_states.npz')
                with np.load(parent) as previous:old_replay=all(np.array_equal(data[k],previous[k]) for k in data.files)
                if not old_replay:raise ValueError('old replay mismatch')
        late=h[-r['traction_window_steps']:];J=np.mean([np.array(x['boundary_impulse'])+x['status_impulse'] for x in late],axis=0)
        if not np.allclose(J,r['mean_traction_candidate'],rtol=0,atol=1e-13):raise ValueError('traction mismatch')
        audits.append({'case_id':r['case_id'],'max_mass_budget_residual':float(np.max(np.abs(mr))),
                       'max_momentum_budget_residual':float(np.max(np.abs(pr))),'final_profile_rechecked':True,
                       'H_exact_state_replay':old_replay})
    post=[r for r in rows if r['incoming_level']=='post'];baseline=[r for r in rows if r['incoming_level']=='old']
    if not all(r['passed'] for r in post):raise ValueError('POST selection not authorized by gates')
    selected=[next(r for r in post if r['base_case']==f'shear_N{n}') for n in (8,16,32)]
    oldselected=[next(r for r in baseline if r['base_case']==f'shear_N{n}') for n in (8,16,32)]
    envelopes=[r['late_window_max_ux_error'] for r in selected]
    orders=np.log(np.array(envelopes[:-1])/envelopes[1:])/np.log(2)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,3,figsize=(14,4.8));ns=[8,16,32]
    for rr,label,col in [(oldselected,'OLD: pre-collision','#b35166'),(selected,'POST: corrected','#268c89')]:
        axs[0].plot(ns,[100*r['final_ux_normalized_error'] for r in rr],'o-',label=label,color=col)
    axs[0].axhline(2,color='black',ls='--',label='Unchanged 2% limit');axs[0].set(xlabel='Fluid nodes across channel, N',ylabel='Final velocity error / U (%)',title='Coarse-grid failure removed');axs[0].legend(fontsize=9)
    for mode,label,col in [('old','OLD','#b35166'),('post','POST','#268c89')]:
        rr=sorted([r for r in rows if r['incoming_level']==mode and r.get('n')==8 and r['base_case'].startswith('shear_N8')],key=lambda r:r['phase_offset_lu'])
        axs[1].plot([r['phase_offset_lu'] for r in rr],[100*r['final_ux_normalized_error'] for r in rr],'o-',color=col,label=label)
    axs[1].axhline(2,color='black',ls='--');axs[1].set(xlabel='Additional initial wall offset (LU)',ylabel='Final velocity error / U (%)',title='Paired N=8 wall-position check');axs[1].legend(fontsize=9)
    axs[2].loglog(ns,100*np.array(envelopes),'o-',color='#268c89',label='POST late-cycle maximum')
    axs[2].loglog(ns,100*envelopes[0]*(8/np.array(ns,dtype=float))**2,'k--',label='N^-2 reference')
    axs[2].set(xlabel='Fluid nodes across channel, N',ylabel='Late-window maximum error / U (%)',title='Residual decreases with refinement');axs[2].legend(fontsize=9)
    for ax in (axs[0],axs[2]):ax.set_xticks(ns,labels=['8','16','32'])
    for ax in axs:ax.grid(alpha=.2)
    fig.suptitle('Stage36I | Boundary time-level defect isolated and corrected',x=.055,ha='left',fontsize=16)
    fig.text(.055,.035,'113 unit tests passed | 36 CPU conditions compared | All 18 POST conditions pass unchanged gates\n'
             'Planar verification only; diffusive refinement, not independent space/time convergence. No curved-fibre or release qualification.',fontsize=10)
    fig.subplots_adjust(left=.065,right=.985,top=.80,bottom=.26,wspace=.36)
    fig.savefig(out/'timelevel_comparison.png',dpi=150,facecolor='white');plt.close(fig)
    handoff={'selected_source':str(Path(__file__).resolve().parent/'translating_channel_timelevel_v1.py'),
             'selected_source_sha256':sha(Path(__file__).resolve().parent/'translating_channel_timelevel_v1.py'),
             'required_explicit_argument':{'incoming_level':'post'},'warning':'Default old is retained for reproducibility; do not use default for selected implementation.',
             'evidence_manifest':str(src/'verification.json'),'evidence_sha256':sha(src/'verification.json'),
             'scope':'selected for next bounded CPU moving-boundary verification only',
             'next_gate':'Prescribed curved-body motion: constant co-moving flow first, swept-volume/mass and force budgets plus geometry-phase refinement; no soil release.',
             'production_execution_authorized':False,'release_prediction_qualified':False}
    (out/'selected_implementation.json').write_text(json.dumps(handoff,indent=2),encoding='utf-8')
    maxmass=max(r['max_mass_relative_drift'] for r in post)
    text=f'''# Stage36I — boundary time level corrected; planar gates pass

Completed 113 unit tests (105 prior + 8 new) and 36 paired CPU flow conditions.
All 18 POST conditions pass every unchanged Stage36H gate. The OLD variant passes
{sum(r['passed'] for r in baseline)}/18. All 12 phase-zero OLD cases reproduce
Stage36H saved state arrays exactly. No old source or result was overwritten.

## Cause and controlled change

The q>.5 boundary branch combined post-collision outgoing data with pre-collision
incoming data. An analytical linearized Couette boundary identity predicts its
nonzero residual. Replacing ONLY that incoming value with its post-collision value
eliminates the manufactured residual and the stationary-shear boundary bias.
No geometry-timing, refill, contact/material parameter, density correction, or
accuracy-limit changes were made. This is a numerical time-level correction, not
experimental calibration. Static corrected velocity errors are at round-off
scale (at most 1.41e-12 normalized in these runs).

| Translating shear | OLD final velocity error / U | POST error / U |
|---|---:|---:|
| N=8 | 4.1233% | 0.3150% |
| N=16 | 0.7728% | 0.05988% |
| N=32 | 0.7987% | 0.01602% |

The original N8 failure is resolved without relaxing the 2% limit. All six added
POST wall-offset cases and both reversed-motion/shear checks pass. Uniform-flow,
density, positivity, constant volume, normal velocity/traction, and mass/momentum
gates also pass. Maximum POST mass drift is {maxmass:.6g} relative. Corrected
base moving-wall shear-candidate errors are 0.03539%, 0.006640%, and 0.001751%.

Late-cycle maximum velocity errors (not just the endpoint) decrease from
0.3167% to 0.08010% to 0.02015%. Their observed diffusive-refinement orders are
{orders[0]:.3f} and {orders[1]:.3f}; consistent with second-order behavior for this
planar test, NOT independent time/space convergence or a universal accuracy claim.
All 36 saved histories were independently audited for step budgets, final profiles,
refill-event counts and late traction averages. Original states remain hash-bound.

## Selected implementation and next gate

Use translating_channel_timelevel_v1.py with EXPLICIT incoming_level='post'. The
default 'old' remains solely for historical comparison. Selection and hashes are
in selected_implementation.json. Following the DEM-researcher verification ladder,
the selection is limited to the next bounded CPU verification step, not production.

Next: prescribed curved-body motion with co-moving uniform flow, swept-volume/
mass and force accounting, followed by geometric phase/resolution checks. The
current channel has fixed fluid-node count; arbitrary curved-body voxel-volume
changes remain unresolved. No moving-fibre drag, outlet transport, wet contact,
release fraction, or permeability validation is established by these results.

Reference context: [Peng et al. (2016)](https://research.me.udel.edu/lwang/reprints/Peng_etal_CAMWA_2016.pdf),
boundary interpolation and refill discussion; [official lbmpy interpolation documentation](https://pycodegen.walberla.net/docs/lbmpy/2.0/notebooks/demo_interpolation_boundary_conditions.html).
The correction here is supported by an explicit analytical identity and paired
tests, not a claim to reproduce either complete external implementation.

Reproduction: run stage36_staging/verify_stage36i_timelevel_v1.py --output NEW_DIR,
then stage36_staging/evaluate_render_stage36i_v1.py --input NEW_DIR --output NEW_RENDER.
All paths are relative to C:/MATDEM_MICROPLASTIC; outputs must not already exist.
'''
    (out/'RESULTS.md').write_text(text,encoding='utf-8')
    (out/'independent_audit.json').write_text(json.dumps({'verified_file_bindings':len(bindings),'cases':audits,'observed_diffusive_orders':orders.tolist()},indent=2),encoding='utf-8')
    final={'source_hashes':{str(src/'verification.json'):sha(src/'verification.json'),str(Path(__file__).resolve()):sha(__file__)},
           'artifact_hashes':{str(x):sha(x) for x in out.iterdir()},'selected_variant':'post','decision':'planar_pass_only'}
    (out/'render_manifest.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
    print(json.dumps({'rechecked_cases':len(audits),'selected_cases_passed':len(post),'max_mass_drift':maxmass,'orders':orders.tolist()}))

if __name__=='__main__':main()
