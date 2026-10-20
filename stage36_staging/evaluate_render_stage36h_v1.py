"""Read-only numerical re-audit of saved runs; write new derived report/figure."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from body_link_extractor_v1 import C


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    src=args.input.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((src/'verification.json').read_text())
    if not manifest['execution_completed'] or not manifest['unit_tests_passed']:raise ValueError('incomplete source')
    verified={}
    for group in ('source_hashes','artifact_hashes','parent_binding_checks'):
        for path,h in manifest[group].items():
            if sha(path)!=h:raise ValueError('hash mismatch '+path)
            verified[path]=h
    rows=json.loads((src/'flow_results.json').read_text())['cases'];audits=[]
    for r in rows:
        history=json.loads((src/(r['case_id']+'_history.json')).read_text())
        mr=[];pr=[]
        for h in history:
            mr.append(h['mass_after']-h['mass_before']-h['collision_mass']-sum(h['boundary_mass'])-sum(h['status_mass']))
            pr.append(np.array(h['momentum_after'])-h['momentum_before']-h['collision_momentum']+
                      np.array(h['boundary_impulse']).sum(axis=0)+np.array(h['status_impulse']).sum(axis=0))
        mr=float(np.max(np.abs(mr)));pr=float(np.max(np.abs(pr)))
        if mr>1e-11 or pr>1e-11:raise ValueError('independent operator budget failed')
        with np.load(src/(r['case_id']+'_states.npz')) as a:
            f=a['final'];y=a['y'];lower=r['n']+np.sqrt(2)/10+r['V_lu']*r['steps'];fluid=(y>lower)&(y<lower+r['n'])
            rho=f[:,fluid].sum(axis=0);u=C.T@f[:,fluid]/rho
            error=float(np.max(np.abs(u[0]-r['U_lu']*(y[fluid]-lower)/r['n']))/max(abs(r['U_lu']),.001))
            if not np.isclose(error,r['final_ux_normalized_error'],atol=1e-14):raise ValueError('profile audit failed')
            events=a['event_states'].shape[0]
            if events!=sum(bool(h['refill_stencils']) for h in history):raise ValueError('event count mismatch')
            # Both attempts used the same numerical source; check actual arrays.
            previous=src.parent/'verification_01'/(r['case_id']+'_states.npz')
            with np.load(previous) as first:
                if any(not np.array_equal(a[k],first[k]) for k in a.files):raise ValueError('export-only rerun changed state')
        late=history[-r['traction_window_steps']:]
        traction=np.mean([np.asarray(h['boundary_impulse'])+h['status_impulse'] for h in late],axis=0)
        if not np.allclose(traction,r['mean_traction_candidate'],rtol=0,atol=1e-13):raise ValueError('traction mismatch')
        audits.append({'case_id':r['case_id'],'mass_budget_max_residual':mr,'momentum_budget_max_residual':pr,
                       'final_profile_recomputed':True,'refill_events':events,'export_rerun_states_identical':True})
    moving=[next(r for r in rows if r['case_id']==f'shear_N{n}') for n in (8,16,32)]
    static=[next(r for r in rows if r['case_id']==f'static_shear_N{n}') for n in (8,16,32)]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(14,4.8))
    colors=['#b25266','#329d9b','#487bc3']
    axes[0].plot([0,1],[0,1],'k--',label='Exact linear shear')
    for r,c in zip(moving,colors):axes[0].plot(r['y_over_H'],np.array(r['ux_final'])/r['U_lu'],'o-',ms=3,label=f"N={r['n']}",color=c)
    axes[0].set(xlabel='Position within moving channel, y/H',ylabel='Tangential velocity, ux/U',title='Complete translating-shear flow');axes[0].legend(fontsize=9)
    for rr,label,c in [(moving,'Translating shear','#487bc3'),(static,'Stationary shear','#329d9b')]:
        axes[1].plot([r['n'] for r in rr],[100*r['final_ux_normalized_error'] for r in rr],'o-',label=label,color=c)
    axes[1].axhline(2,color='#b25266',ls='--',label='Fixed 2% limit')
    axes[1].set(xlabel='Fluid nodes across channel, N',ylabel='Maximum velocity error / U (%)',title='Coarsest moving case fails')
    axes[1].legend(fontsize=9);axes[1].set_xticks([8,16,32])
    axes[2].plot([r['n'] for r in moving],[100*r['wall_shear_relative_error'] for r in moving],'o-',color='#487bc3',label='Late traction candidate')
    axes[2].axhline(5,color='#b25266',ls='--',label='Fixed 5% limit')
    axes[2].set(xlabel='Fluid nodes across channel, N',ylabel='Mean wall-shear error (%)',title='Boundary + mask-change ledger')
    axes[2].set_xticks([8,16,32]);axes[2].set_ylim(0,5.6);axes[2].legend(fontsize=9)
    for ax in axes:ax.grid(alpha=.18)
    fig.suptitle('Stage36H | Full moving-boundary CPU test: partial pass',x=.05,ha='left',fontsize=16)
    fig.text(.05,.035,'105 unit tests passed | 11 of 12 benchmark conditions pass all gates | Uniform flow preserved; mass drift < 7.1e-13\n'
             'Prescribed planar motion only. Final velocity error is not monotonic under refinement. No moving-fibre or release qualification.',fontsize=10)
    fig.subplots_adjust(left=.06,right=.985,top=.81,bottom=.25,wspace=.35)
    fig.savefig(out/'translating_channel.png',dpi=150,facecolor='white');plt.close(fig)
    failed=[r['case_id'] for r in rows if not r['passed']];maxmass=max(r['max_mass_relative_drift'] for r in rows)
    report=f'''# Stage36H — complete translating-channel test: partial pass

105 unit tests passed. All 12 unique CPU flow conditions completed; {12-len(failed)}/12
passed every predeclared planar gate. The failed case is **{', '.join(failed)}**:
4.1233% final velocity error exceeds the unchanged 2% limit.

Unlike Stage36G's isolated mask updates, these runs include collision, streaming,
moving interpolated walls, refill, and cell removal on every time step. Every
moving case produced actual cover/uncover events. The rejected pooling method
was not used. Geometry is planar with constant fluid-node count, NOT a fibre.

| Moving shear grid | Final velocity error / U | Mean wall-shear candidate error |
|---|---:|---:|
| N=8 | 4.1233% — fail | 3.9646% |
| N=16 | 0.7728% | 1.8255% |
| N=32 | 0.7987% | 0.8662% |

Uniform translation and rest pass their 1e-10 velocity/density limits. All cases
pass the per-step mass/momentum ledger gates and global mass gate; maximum
relative mass drift is {maxmass:.6g}. Positivity and exact zero solid populations
are enforced throughout. All 12 histories, final profiles, event counts and late
traction averages were independently rechecked from archived data.

**Bounded interpretation:** the full planar step removes the mass/uniform-field
conflict seen in the isolated mask test. It does NOT qualify arbitrary moving
geometry. Fine-grid final velocity errors are non-monotonic, and reverse-motion
N16 error is 1.9167%, so a general convergence-order claim is unsupported.
The wall quantity is the recorded boundary-plus-status momentum-exchange
candidate, compared over five whole cell-crossing periods; it is not yet a
qualified force law for moving curved particles. No body force was applied to
conceal a ledger residual. Static controls also retain small boundary errors.

The first run completed its flow calculations but hit a numpy-boolean JSON export
error. It is preserved in verification_01. A serialization-only verifier revision
reran the same conditions in verification_02; all saved state arrays match exactly.
Thus 12 unique conditions were executed twice, not 24 independent benchmarks.
The numerical solver and gates were unchanged.

Following the DEM-researcher verification ladder, retain the coarse-grid failure
and investigate wall-distance/time-level and refill-phase sensitivity next. Use
the static controls to separate boundary error from motion/refill error. Freeze a
new bounded comparison before executing; do not loosen gates or promote directly
to curved moving fibres. Release fractions remain unverified; no GPU/DEM/YADE or
production campaign was started.

Method source: Peng et al. (2016), interpolation equations 13/15 and refill
section 5.1.1 ([primary paper](https://research.me.udel.edu/lwang/reprints/Peng_etal_CAMWA_2016.pdf)).
This is a CPU BGK adaptation with explicitly documented operator timing, not a
reproduction or validation of their complete MRT implementation.

Authoritative evidence: ../verification_02/verification.json, flow_results.json,
all per-case history/state bundles, and independent_audit.json in this directory.
Figure: translating_channel.png. Source contract:
C:/MATDEM_MICROPLASTIC/stage36_staging/STAGE36H_TRANSLATING_CHANNEL_CONTRACT.md
'''
    (out/'RESULTS.md').write_text(report,encoding='utf-8')
    (out/'independent_audit.json').write_text(json.dumps({'verified_bindings':len(verified),'cases':audits},indent=2),encoding='utf-8')
    result={'source_hashes':{str(src/'verification.json'):sha(src/'verification.json'),str(Path(__file__).resolve()):sha(__file__)},
            'artifact_hashes':{str(x):sha(x) for x in out.iterdir()},'decision':'partial_pass_no_promotion'}
    (out/'render_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'failed_cases':failed,'max_mass_relative_drift':maxmass,'independent_rechecks':len(audits),'verified_bindings':len(verified)}))


if __name__=='__main__':main()
