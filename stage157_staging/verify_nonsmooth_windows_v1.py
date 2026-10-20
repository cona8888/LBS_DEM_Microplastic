"""Prospective nonsmooth-observable verification, with two new finer runs.

No change to equations, initial states or Stage155's failed verdict. The revised
claim excludes uniform instantaneous velocity accuracy across ideal rigid impacts.
"""
from pathlib import Path
import copy
import datetime
import os
import sys
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage156_staging'))
import diagnose_impacts_v2 as diagnostic
diag=diagnostic.job
old=diag.old
api,model,engine=old.api,old.model,old.engine
BASE='nonsmooth_window_verification_20260922'
DESIGN=ROOT/'stage157_designs'/BASE/'design_01.json'
RUN=ROOT/'stage157_runs'/BASE/'run_01'
OUT=ROOT/'stage157_evaluations'/BASE/'evaluation_01'
AUDIT=OUT.parent/'independent_audit_01'
FACTORS=[.5,.25,.125]
IMPULSE_WINDOWS={'engagement':[[.555,.55505],[.57030,.57050]],
                 'release':[[1.742,1.74205],[1.74945,1.74970]]}


def prepare():
    prior=api.read(old.DESIGN);old.verify(prior)
    diag.verify(api.read(diag.DESIGN))
    evidence=api.read(diag.OUT/'results.json')
    api.require(evidence['diagnostic_integrity_passed'] and not evidence['application_accuracy_accepted'],'diagnostic-only source')
    paths=[old.DESIGN,old.OUT/'results.json',old.OUT/'completion.json',old.AUDIT/'results.json',old.AUDIT/'completion.json',
           diag.DESIGN,diag.OUT/'results.json',diag.OUT/'completion.json',diag.OUT/'analytical_toy.json']
    inputs={str(p):api.sha(p) for p in paths}
    inputs.update(api.read(old.OUT/'results.json')['artifacts'])
    d={'stage':'Stage157','question':'Do two new finer runs support convergence of integral velocity and contact impulse, pose and event timing, without a uniform velocity claim at impacts?',
       'windows':prior['windows'],'factors':FACTORS,'base_spec':prior['base_spec'],
       'reused_factors':[.5,.25],'new_factor':.125,'input_state':'Exactly the two full Stage155 prepared checkpoints. No pose/velocity projection, reset or event-time alignment.',
       'physical_changes':[],'algorithm_changes':[],'generated_source_digest':api.digest(old.parent.prior.candidate.GENERATED_SOURCE),
       'accuracy':prior['accuracy'],
       'revised_observable':'Velocity is the piecewise-constant generalized velocity actually used for each accepted pose interval. Compare its norm difference by exact integration over the common physical clock, divided by duration and U. No masking, alignment or cancellation of vector components.',
       'velocity_L1_mean_limit_over_U':prior['accuracy']['limits']['generalized_velocity_relative'],
       'impulse_windows_s':IMPULSE_WINDOWS,
       'impulse_metric':'For each fixed time window, sum all generalized contact reactions times their overlap duration with that window. Compare impulses in the norm of inverse mass evaluated at the unchanged initial checkpoint, divided by U. This is an impulse-equivalent velocity, not an angular-momentum balance with constant world-frame inertia.',
       'impulse_limit_equivalent_velocity_over_U':prior['accuracy']['limits']['generalized_velocity_relative'],
       'primary_gates':['All levels completed at identical endpoints with original health/clock/provenance gates, no new rejections or unqualified fallback.',
                        'Both coarser full pose traces and the finest endpoint pair satisfy original limits; endpoint errors show original refinement reduction.',
                        'Both coarser whole-window mean L1 velocity errors satisfy 0.005 U; adjacent-level L1 error decreases by at least the inherited 0.8 factor.',
                        'All selected contact-impulse windows satisfy 0.005 U equivalent error against finest, and adjacent-level impulse errors decrease by the inherited 0.8 factor unless below the inherited noise floor.',
                        'Original sustained contact events are present, with midpoint spread <=4 maximum coarse accepted steps.',
                        'Selected frozen-pose replays reproduce every sampled velocity within 1e-8 U, and momentum/work balance <=1e-8.'],
       'original_failed_gate':'Report original uniform linearly interpolated velocity differences, but do not use them to claim pointwise impact-velocity accuracy. Stage155 remains failed; this is a prospectively different, narrower verification contract, not a retcon.',
       'evidence_role':'Stage155 windows are now development cases. New finer runs are solution-verification evidence, not independent empirical validation or new physical conditions.',
       'budget':{'new_cases':2,'max_calls_per_case':12,'step_cap':2500,'cooperative_seconds_per_call':45.,'maximum_replay_calls':2000,'workers':1,'threads':1,'estimated_new_integration_minutes':[6,10]},
       'stop':'No tolerance relaxation, extra levels or unbounded retries after a failed primary gate.',
       'claim':'Two conditional rigid-fibre windows in prescribed CPD6 flow only; no uniform instantaneous velocity accuracy, population export, permanent retention, fresh full path, empirical validation or production promotion.',
       'sources':{str(Path(m.__file__).resolve()):api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents},
       'inputs':inputs}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['inputs']);api.verify_mapping(d['sources'])
    old.verify(api.read(old.DESIGN));diag.verify(api.read(diag.DESIGN))
    api.require(d['factors']==FACTORS and d['impulse_windows_s']==IMPULSE_WINDOWS,'prospective selections')
    api.require(d['generated_source_digest']==api.digest(old.parent.prior.candidate.GENERATED_SOURCE),'unchanged algorithm')


def setup(d,wi):
    w=d['windows'][wi];spec=copy.deepcopy(d['base_spec'])
    spec['horizon_s']=w['horizon_s'];spec['horizon_pv']=w['horizon_s']*spec['field_metadata']['pv_per_second']
    for k in api.DT_CONTROLS:spec['config']['numerics'][k]*=d['new_factor']
    binding=api.digest([d['binding'],w['id'],d['new_factor']])
    source=old.read_record(old.RUN/w['id']/'seed.json')['result']['checkpoint']
    return spec,binding,model.checkpoint(spec,binding,source,True)


def check_segment(d,r,before,spec,binding):
    api.require(r['spec']==spec and r['design_sha256']==api.sha(DESIGN),'segment identity')
    effective=model.binding_for(binding,True)
    api.require(r['input_checkpoint_sha256']==api.digest(before) and r['effective_binding']==effective,'input/effective binding')
    api.require(old.parent.prior.s.check_record(r,before,spec,effective)['passed'],'health/clock/contract')
    api.require(len(r['backend_calls'])==1 and r['backend_calls'][0]['enabled'],'rigid live backend')
    api.require(len(r['rows'])<=d['budget']['step_cap'],'step budget')
    old.parent.segment_guard(r['result'],before,spec['horizon_s'])


def read_new(d,wi):
    folder=RUN/d['windows'][wi]['id'];spec,binding,initial=setup(d,wi);before=initial
    rows=[];cost=0.
    paths=sorted(folder.glob('segment_[0-9][0-9].json'))
    api.require(0<len(paths)<=d['budget']['max_calls_per_case'],'segment count')
    for i,p in enumerate(paths,1):
        api.require(p.name==f'segment_{i:02d}.json','segment order')
        seal=api.read(p.with_suffix('.seal.json'));api.require(seal['record_sha256']==api.sha(p) and seal['design_sha256']==api.sha(DESIGN),'segment seal')
        r=api.read(p);check_segment(d,r,before,spec,binding)
        api.require(i==len(paths) or r['result']['status'] in ['paused_checkpoint','incomplete_budget'],'no post-completion run')
        rows.extend(r['rows']);cost+=r['result']['runtime_seconds'];before=r['result']['checkpoint']
    api.require(r['result']['status']=='present_at_horizon','matched endpoint')
    return {'result':r['result'],'rows':rows,'spec':spec,'cost_s':cost,'segments':len(paths)}


def records(d,wi):
    prior=api.read(old.DESIGN)
    return [old.join_case(prior,wi,f) for f in d['reused_factors']]+[read_new(d,wi)]


def collect_impulses(d,wi,recs,field,geometry):
    w=d['windows'][wi];seed=old.read_record(old.RUN/w['id']/'seed.json')['result']['checkpoint']['state']
    cfg=d['base_spec']['config'];a,b,_=cfg['prolate_semiaxes_m'];U=cfg['target_mean_interstitial_velocity_m_s']
    M,_=diag.backend.generalized_mass_matrix(np.array(seed['p']),a,b,cfg['particle_density_kg_m3'],cfg['fluid_density_kg_m3'],cfg['added_mass_fraction'])
    levels=[];calls=0
    with old.hot.scope(),old.engine.runtime.repair_scope():
        for factor,r in zip(FACTORS,recs):
            totals=[np.zeros(6) for _ in IMPULSE_WINDOWS[w['id']]];samples=[]
            for i,row in enumerate(r['rows']):
                left=seed['t'] if i==0 else r['rows'][i-1]['time_s'];right=row['time_s']
                overlaps=[max(0.,min(right,stop)-max(left,start)) for start,stop in IMPULSE_WINDOWS[w['id']]]
                if not any(overlaps):continue
                prev=seed if i==0 else {'x':r['rows'][i-1]['position_m'],'p':r['rows'][i-1]['orientation'],'q':r['rows'][i-1]['velocity_generalized'],'t':left,'recovery':seed['recovery']}
                q,detail=diag.replay(field,geometry,r['spec'],prev,row['dt_s']);calls+=1
                api.require(calls<=d['budget']['maximum_replay_calls']//2,'replay budget')
                error=float(np.linalg.norm(q-row['velocity_generalized'])/U)
                api.require(error<=1e-8 and detail['momentum_residual']<=1e-8 and detail['work_balance_relative']<=1e-8,'replay/closure')
                for k,span in enumerate(overlaps):totals[k]+=np.array(detail['impulse_generalized'])*(span/row['dt_s'])
                # Compact sampled telemetry, not full pose duplication.
                samples.append({'time_s':right,'dt_s':row['dt_s'],'overlap_s':overlaps,'replay_error_over_U':error,
                                **{k:detail[k] for k in ['impulse_generalized','momentum_residual','work_balance_relative','contact_work_J','kinetic_change_frozen_mass_J','implicit_numerical_loss_J']}})
            levels.append({'factor':factor,'integrated_generalized_impulses':[v.tolist() for v in totals],'samples':samples})
    compare=lambda A,B:[float(np.linalg.norm(np.linalg.solve(M,np.array(x)-np.array(y)))/U) for x,y in zip(A['integrated_generalized_impulses'],B['integrated_generalized_impulses'])]
    return {'windows_s':IMPULSE_WINDOWS[w['id']],'mass_reference':'unchanged seed orientation','levels':levels,'replay_calls':calls,
            'equivalent_velocity_errors_to_finest':[compare(level,levels[-1]) for level in levels[:-1]],
            'adjacent_level_equivalent_velocity_errors':[compare(a,b) for a,b in zip(levels,levels[1:])]}


def summary(d,wi,recs,impulses):
    w=d['windows'][wi];seed=old.read_record(old.RUN/w['id']/'seed.json')['result']['checkpoint']
    prior=api.read(old.DESIGN);U=d['base_spec']['config']['target_mean_interstitial_velocity_m_s']
    limits=d['accuracy']['limits'];ratio=d['accuracy']['error_reduction_ratio_max'];noise=d['accuracy']['noise_floor']
    reduced=lambda a,b: b<=ratio*a or max(a,b)<noise
    endpoints=[old.parent.prior.w.compare(a['result'],b['result'],b['spec']) for a,b in zip(recs,recs[1:])]
    trace=[old.parent.prior.common_trace(recs[-1]['rows'],r,seed) for r in recs[:-1]]
    l1=[diag.piecewise_l1(r['rows'],recs[-1]['rows'],seed['state']['t'],w['horizon_s'],U) for r in recs[:-1]]
    adjacent_l1=[diag.piecewise_l1(a['rows'],b['rows'],seed['state']['t'],w['horizon_s'],U) for a,b in zip(recs,recs[1:])]
    events=[old.observed_event(prior,wi,r) for r in recs]
    spread=max(e['midpoint_s'] for e in events)-min(e['midpoint_s'] for e in events) if all(events) else None
    event_limit=4*max(r['dt_s'] for r in recs[0]['rows'])
    ic=impulses['adjacent_level_equivalent_velocity_errors']
    checks={'endpoint_limits_and_refinement':all(endpoints[1][k]<=limit and reduced(endpoints[0][k],endpoints[1][k]) for k,limit in limits.items()),
            'whole_pose_traces':all(all(t[k]<=limits[k] for k in ['position_over_b','axis_vector_norm']) for t in trace),
            'whole_L1_velocity_limits':all(r['mean_norm_over_scale']<=d['velocity_L1_mean_limit_over_U'] for r in l1),
            'L1_refinement':reduced(adjacent_l1[0]['mean_norm_over_scale'],adjacent_l1[1]['mean_norm_over_scale']),
            'impulse_limits':all(e<=d['impulse_limit_equivalent_velocity_over_U'] for level in impulses['equivalent_velocity_errors_to_finest'] for e in level),
            'impulse_refinement':all(reduced(a,b) for a,b in zip(*ic)),
            'events':spread is not None and spread<=event_limit,
            'unchanged_verdicts':all(all(r['result'][k]==recs[-1]['result'][k] for k in ['status','persistent_contact_observed','dwell_is_absorbing']) for r in recs)}
    return {'id':w['id'],'passed':all(checks.values()),'checks':checks,'endpoint_errors':endpoints,
            'whole_trace_original_metrics':trace,'mean_L1_velocity_to_finest':l1,'adjacent_L1_velocity':adjacent_l1,
            'events':events,'event_spread_s':spread,'event_spread_limit_s':event_limit,
            'impulse_errors_to_finest':impulses['equivalent_velocity_errors_to_finest'],'adjacent_impulse_errors':ic,
            'cost':[{'factor':f,'reused':f!=d['new_factor'],'steps':len(r['rows']),'runtime_s':r['cost_s']} for f,r in zip(FACTORS,recs)]}


def evaluate(d):
    old.parent.configure();spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    reports=[]
    for wi,w in enumerate(d['windows']):
        recs=records(d,wi);impulses=collect_impulses(d,wi,recs,field,geometry)
        api.write(OUT/f"{w['id']}_impulses.json",impulses,raw=True)
        reports.append(summary(d,wi,recs,impulses))
    result={'stage':'Stage157','passed':all(w['passed'] for w in reports),'windows':reports,'design_sha256':api.sha(DESIGN),
            'stage155_remains_failed':True,'uniform_instantaneous_velocity_claim':False,'production_promotion':False,'claim':d['claim'],
            'artifacts':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()},
            'impulse_artifacts':{str(p):api.sha(p) for p in OUT.glob('*_impulses.json')}}
    verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'passed':result['passed']})
    print('STAGE157',result['passed'],[(w['id'],w['checks']) for w in reports],flush=True)


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'argv':sys.argv,'python':sys.version,'design_sha256':api.sha(DESIGN),'threads':{k:os.environ.get(k) for k in old.parent.THREADS}})
    old.parent.configure()
    for wi,w in enumerate(d['windows']):
        folder=RUN/w['id'];folder.mkdir(exist_ok=False);spec,binding,cp=setup(d,wi)
        for n in range(1,d['budget']['max_calls_per_case']+1):
            before=copy.deepcopy(cp);ncalls=len(model.calls)
            with old.hot.scope(),old.parent.prior.candidate.scope(True):
                result,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+d['budget']['step_cap'])
            r={'result':result,'rows':rows,'spec':spec,'design_sha256':api.sha(DESIGN),'input_checkpoint_sha256':api.digest(before),'effective_binding':model.binding_for(binding,True),'backend_calls':copy.deepcopy(model.calls[ncalls:])}
            r['checks']=old.parent.prior.s.check_record(r,before,spec,r['effective_binding'])
            p=folder/f'segment_{n:02d}.json';api.write(p,r,raw=True);api.write(p.with_suffix('.seal.json'),{'record_sha256':api.sha(p),'design_sha256':api.sha(DESIGN)})
            check_segment(d,r,before,spec,binding)
            print(w['id'],n,result['status'],len(rows),'t=',result['time_s'],flush=True)
            if result['status']=='present_at_horizon':break
            cp=result['checkpoint']
        api.require(result['status']=='present_at_horizon','prospective case budget exhausted')
    OUT.mkdir(parents=True,exist_ok=False);evaluate(d)


def audit():
    d=api.read(DESIGN);verify(d);r=api.read(OUT/'results.json')
    api.require(api.read(OUT/'completion.json')['results_sha256']==api.sha(OUT/'results.json'),'evaluation seal')
    api.verify_mapping(r['artifacts']);api.verify_mapping(r['impulse_artifacts']);api.require(not list(RUN.rglob('failure.json')),'no runtime failure')
    old.parent.configure();spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    recomputed=[]
    for wi,w in enumerate(d['windows']):
        recs=records(d,wi);imp=api.read(OUT/f"{w['id']}_impulses.json")
        api.require(collect_impulses(d,wi,recs,field,geometry)==imp,'independent frozen-pose replay, coverage and impulse errors')
        # Independently sum the raw selected replay impulses and overlaps.
        for level in imp['levels']:
            totals=[np.zeros(6) for _ in imp['windows_s']]
            for s in level['samples']:
                api.require(s['replay_error_over_U']<=1e-8 and s['momentum_residual']<=1e-8 and s['work_balance_relative']<=1e-8,'replay health')
                for k,span in enumerate(s['overlap_s']):totals[k]+=np.array(s['impulse_generalized'])*span/s['dt_s']
            api.require(np.allclose(totals,level['integrated_generalized_impulses'],rtol=1e-13,atol=1e-30),'raw impulse sum')
        recomputed.append(summary(d,wi,recs,imp))
    api.require(recomputed==r['windows'] and r['passed']==all(w['passed'] for w in recomputed),'raw record evaluation')
    AUDIT.mkdir(parents=True,exist_ok=False)
    report={'audit_integrity_passed':True,'scientific_gates_passed':r['passed'],'evaluation_sha256':api.sha(OUT/'results.json'),'windows':recomputed,'claim':d['claim'],'production_promotion':False}
    api.write(AUDIT/'results.json',report,raw=True);api.write(AUDIT/'completion.json',{'results_sha256':api.sha(AUDIT/'results.json'),'audit_integrity_passed':True})
    print('AUDIT PASS; SCIENTIFIC',r['passed'],flush=True)


if __name__=='__main__':
    owned=False
    try:
        if sys.argv[1:]==['prepare']:prepare()
        elif sys.argv[1:]==['run']:
            api.require(not RUN.exists() and not OUT.exists(),'immutable run exists; no restart')
            owned=True
            run()
        elif sys.argv[1:]==['audit']:audit()
        else:raise ValueError('Use prepare, run or audit')
    except Exception as e:
        if owned and RUN.exists() and not (RUN/'failure.json').exists():
            api.write(RUN/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()})
        raise
