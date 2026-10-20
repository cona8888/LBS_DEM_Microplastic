"""Read-only local endpoint diagnosis and an analytical impact/release toy.

No application trajectory is advanced or aligned. A counterexample can refute
the necessity of a monotone error-ratio gate, not qualify the application.
"""
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage159_staging'))
import local_impact_refinement_v1 as prior
api=prior.api
BASE='endpoint_phase_diagnosis_20260922'
DESIGN=ROOT/'stage160_designs'/BASE/'design_01.json'
OUT=ROOT/'stage160_evaluations'/BASE/'diagnosis_01'


def toy(timpact,n):
    # x>=0, m=1, a=+1 away from wall, initial v=-1. Choose x0 so the
    # first exact hit is timpact. Perfectly inelastic impact, immediate release.
    # For T=1, exact v=1-timpact, x=(1-timpact)^2/2.
    h=1./n;x=timpact-.5*timpact*timpact;v=-1.;P=0.;minx=x
    for k in range(n):
        free=v+h
        q=max(free,-x/h)
        P+=q-free;x+=h*q;v=q;minx=min(x,minx)
    exact_v=1-timpact;exact_x=.5*(1-timpact)**2;exact_P=1-timpact
    return {'n':n,'dt_s':h,'x':x,'v':v,'impulse':P,'minimum_x':minx,
            'x_error':abs(x-exact_x),'v_error':abs(v-exact_v),'impulse_error':abs(P-exact_P)}


def prepare():
    prior.verify(api.read(prior.DESIGN));audit=prior.OUT.parent/'failure_audit_01'
    api.require(api.read(audit/'completion.json')['results_sha256']==api.sha(audit/'results.json'),'failure audit seal')
    failed=api.read(audit/'results.json');api.require(failed['audit_integrity_passed'] and not failed['scientific_gates_passed'],'preserved failed verdict')
    inputs=dict(failed['artifacts'])
    for p in [prior.DESIGN,audit/'results.json',audit/'completion.json']:inputs[str(p)]=api.sha(p)
    d={'stage':'Stage160','application_action':'Read only all three Stage159 engagement traces; no new contact solve or trajectory.',
       'toy':'Unit mass, x>=0, outward acceleration +1, initial velocity -1, inelastic impact, immediate outward release. Known piecewise exact solution. Same implicit gap constraint q=max(v+h,-x/h).',
       'toy_impact_times_s':np.linspace(.15,.45,31).tolist(),'toy_step_counts':[64,128,256,512,1024],
       'toy_checks':['Nonpenetration >=-1e-12; terminal discrete momentum closes <=1e-12.',
                     'For all frozen cases, finest absolute x/v/impulse errors are smaller than coarsest.',
                     'Report, without selecting cases, every adjacent-refinement-ratio violation. A toy counterexample is not an application acceptance gate.'],
       'application_metrics':['Endpoint vector-difference directions and norm ratios.',
                              'Unaligned cross-level pose and velocity discrepancies before contact and after contact at common finest-grid sample times.',
                              'Contact-indicator brackets and event-grid placement; no assertion of exact continuous contact time.'],
       'claim':'Diagnostic evidence only. Preserve Stage159 failure. No production qualification, no release fraction, no empirical validation.',
       'inputs':inputs,'sources':{str(Path(__file__).resolve()):api.sha(__file__)}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['inputs']);api.verify_mapping(d['sources']);prior.verify(api.read(prior.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);OUT.mkdir(parents=True,exist_ok=False)
    toy_results=[];violations=[]
    for t in d['toy_impact_times_s']:
        levels=[toy(t,n) for n in d['toy_step_counts']]
        api.require(all(x['minimum_x']>=-1e-12 and abs(x['v']-x['impulse'])<=1e-12 for x in levels),'toy nonpenetration and momentum')
        api.require(all(levels[-1][k]<levels[0][k] for k in ['x_error','v_error','impulse_error']),'toy error reduction across full resolution span')
        for k in ['x','v','impulse']:
            differences=[abs(b[k]-a[k]) for a,b in zip(levels,levels[1:])]
            for i,(a,b) in enumerate(zip(differences,differences[1:])):
                if b>.8*a and max(a,b)>1e-10:
                    violations.append({'impact_s':t,'observable':k,'coarse_steps':levels[i]['n'],
                                       'adjacent_errors':[a,b],'ratio':b/a if a else None,
                                       'errors_to_exact':[levels[j][k+'_error'] for j in [i,i+1,i+2]]})
        toy_results.append({'impact_s':t,'levels':levels})
    source=api.read(prior.DESIGN);recs=[prior.joined(source,0,f) for f in prior.FACTORS]
    summary=api.read(prior.OUT/'engagement_summary.json');cfg=source['base_spec']['config'];U=cfg['target_mean_interstitial_velocity_m_s'];b=cfg['prolate_semiaxes_m'][1]
    endpoint={};keys=[('position_m','position_over_b',b),('orientation','axis_vector_norm',1.),('velocity_generalized','generalized_velocity_relative',U)]
    for key,label,scale in keys:
        vals=[np.array(r['rows'][-1][key]) for r in recs];diffs=[(y-x)/scale for x,y in zip(vals,vals[1:])]
        cosine=float(diffs[0]@diffs[1]/(np.linalg.norm(diffs[0])*np.linalg.norm(diffs[1])))
        endpoint[label]={'adjacent_vectors':[x.tolist() for x in diffs],'cosine_between_adjacent_differences':cosine,
                         'adjacent_norms':[float(np.linalg.norm(x)) for x in diffs]}
    periods={'precontact':[summary['entry_s'],min(e['bracket_s'][0] for e in summary['events'])],
             'postcontact':[max(e['bracket_s'][1] for e in summary['events']),summary['horizon_s']]}
    profile={}
    for name,(lo,hi) in periods.items():
        times=np.array([x['time_s'] for x in recs[-1]['rows'] if lo<=x['time_s']<=hi])
        values={}
        for key,label,scale in keys:
            vectors=[]
            for r in recs:
                t=[x['time_s'] for x in r['rows']];q=np.array([x[key] for x in r['rows']])
                vectors.append(np.column_stack([np.interp(times,t,q[:,i]) for i in range(q.shape[1])]))
            values[label]={'adjacent_max':[float(np.linalg.norm(y-x,axis=1).max()/scale) for x,y in zip(vectors,vectors[1:])],
                           'note':'Unshifted linear interpolation is diagnostic only; it is not an impact velocity accuracy gate.'}
        profile[name]={'physical_window_s':[lo,hi],'samples':len(times),'metrics':values}
    result={'diagnostic_integrity_passed':True,'toy_cases':toy_results,'toy_nonmonotone_adjacent_comparisons':violations,
            'toy_nonmonotone_count':len(violations),'monotone_adjacent_ratio_not_necessary_for_toy_convergence':bool(violations),
            'application_endpoint_vectors':endpoint,'application_unaligned_profiles':profile,
            'application_event_brackets':summary['events'],
            'interpretation':'Opposing endpoint difference vectors and contact-localized changes can support a grid-phase hypothesis; they do not isolate it causally. Phase-varied application grids are required before changing the application verification contract.',
            'prior_stage159_passed':False,'application_accuracy_accepted':False,'production_promotion':False,
            'design_sha256':api.sha(DESIGN),'claim':d['claim']}
    verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'diagnostic_integrity_passed':True})
    print('DIAGNOSIS toy nonmonotone',len(violations),'endpoint',endpoint,flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('Use prepare or run')
