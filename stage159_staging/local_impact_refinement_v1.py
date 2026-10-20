"""Six bounded conditional tests; not an adaptive production controller.

Prepare full checkpoints by exact replay of healthy archived prefixes, then use
three finer timesteps only over fixed sub-millisecond contact-event windows.
The common entry state isolates local integration error from inherited history.
"""
from pathlib import Path
import copy
import datetime
import os
import sys
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage158_staging'))
import verify_roundoff_closure_v1 as verified
fix=verified.fix;job=verified.job
api,old,diag,model,engine=job.api,job.old,job.diag,job.model,job.engine
BASE='local_impact_refinement_20260922'
DESIGN=ROOT/'stage159_designs'/BASE/'design_01.json'
RUN=ROOT/'stage159_runs'/BASE/'run_01'
OUT=ROOT/'stage159_evaluations'/BASE/'evaluation_01'
FACTORS=[.0625,.03125,.015625]
WINDOWS=[{'id':'engagement','source_segment':4,'next_segment':5,'entry_cutoff_s':.5702,
          'horizon_s':.57065,'impulse_window_s':[.57030,.57050],'grain_id':3,'after_present':True},
         {'id':'release','source_segment':2,'next_segment':3,'entry_cutoff_s':1.74935,
          'horizon_s':1.74985,'impulse_window_s':[1.74945,1.74970],'grain_id':2,'after_present':False}]


def source_path(w,n):return job.RUN/w['id']/f'segment_{n:02d}.json'


def prepare():
    verified.verify(api.read(verified.DESIGN));job.verify(api.read(job.DESIGN))
    folders=[verified.OUT,verified.OUT.parent/'independent_audit_01']
    inputs={}
    for folder in folders:
        api.require(api.read(folder/'completion.json')['results_sha256']==api.sha(folder/'results.json'),'arithmetic evidence seal')
        for p in [folder/'results.json',folder/'completion.json']:inputs[str(p)]=api.sha(p)
    api.require(api.read(verified.OUT/'results.json')['passed'],'arithmetic qualification')
    entries=[]
    for w in WINDOWS:
        src=api.read(source_path(w,w['source_segment']))
        nxt=api.read(source_path(w,w['next_segment']))
        api.require(src['result']['status'] in ['paused_checkpoint','incomplete_budget'] and src['checks']['passed'],'healthy entry source')
        count=sum(r['time_s']<=w['entry_cutoff_s'] for r in nxt['rows'])
        api.require(0<count<=2500,'bounded prefix replay')
        entries.append({'steps':count,'exact_time_s':nxt['rows'][count-1]['time_s']})
        for n in [w['source_segment'],w['next_segment']]:
            p=source_path(w,n);seal=p.with_suffix('.seal.json')
            api.require(api.read(seal)['record_sha256']==api.sha(p),'archived segment seal')
            inputs[str(p)]=api.sha(p);inputs[str(seal)]=api.sha(seal)
    d={'stage':'Stage159','question':'Does short-window refinement resolve the contact impulse at unchanged physical settings?',
       'windows':WINDOWS,'entries':entries,'factors':FACTORS,'base_spec':api.read(job.DESIGN)['base_spec'],
       'accuracy':api.read(job.DESIGN)['accuracy'],'impulse_and_L1_limit_over_U':.005,
       'local_event_persistence_s':.0001,'event_midpoint_spread_coarse_steps':4.,
       'method':'Replay the healthy Stage157 factor-0.125 prefix exactly into a new owned checkpoint; all three levels use that same full state. No projection, velocity reset, event alignment or masked trace samples. Stage158 changes only arithmetic certification.',
       'evidence_role':'Conditional development solution verification; shared upstream trajectory error is not estimated. These local windows do not establish full-window or full-path accuracy and are not a production event detector.',
       'gates':['Exact entry-prefix replay and finest-level 100 versus 37+63 restart.',
                'All segments satisfy original health, balance, provenance and exact-clock gates, with no new rejected trials.',
                'Whole local pose and mean L1 velocity errors to finest obey inherited caps. Finest endpoint pair and adjacent L1 errors show <=0.8 refinement ratio unless below 1e-10 noise.',
                'Both coarser fixed-clock integrated impulses differ from finest by <=0.005 U-equivalent, with <=0.8 adjacent-error refinement ratio.',
                'Prescribed event occurs at every level, persists for the frozen local 100 microseconds, and midpoint spread <=4 coarse steps. This is not the original 1-ms persistence claim.',
                'All impulse replays match recorded q within 1e-8 U and close momentum/work within 1e-8.'],
       'budget':{'windows':2,'levels_per_window':3,'maximum_seed_steps_per_window':2500,'preflight_calls_per_window':3,
                 'step_cap':2500,'max_calls_per_level':3,'max_impulse_replays_per_window':3500,'threads':1,
                 'workers':1,'cooperative_seconds_per_call':45.,'estimated_minutes':[2,5]},
       'stop':'Stop on first runtime, integrity or primary scientific failure. No extra refinement levels, retries or relaxed thresholds.',
       'inputs':inputs,
       'sources':{str(Path(m.__file__).resolve()):api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents},
       'physical_changes':[],'production_promotion':False}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),'entries',entries,flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    verified.verify(api.read(verified.DESIGN));job.verify(api.read(job.DESIGN))
    api.require(d['windows']==WINDOWS and d['factors']==FACTORS,'frozen selections')


def execute(d,spec,binding,cp,path,steps):
    before=copy.deepcopy(cp);calls=len(model.calls);certs=len(fix.telemetry)
    with old.hot.scope(),old.parent.prior.candidate.scope(True),fix.scope():
        result,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+steps)
    rec={'result':result,'rows':rows,'spec':spec,'input_checkpoint_sha256':api.digest(before),
         'effective_binding':model.binding_for(binding,True),'design_sha256':api.sha(DESIGN),
         'backend_calls':copy.deepcopy(model.calls[calls:]),'step_cap':steps,'certificates':copy.deepcopy(fix.telemetry[certs:])}
    rec['checks']=old.parent.prior.s.check_record(rec,before,spec,rec['effective_binding'])
    api.write(path,rec,raw=True);api.write(path.with_suffix('.seal.json'),{'record_sha256':api.sha(path),'design_sha256':api.sha(DESIGN)})
    check(rec,before,spec,binding)
    print(path.relative_to(RUN),result['status'],len(rows),'t=',result['time_s'],flush=True)
    return rec


def check(r,before,spec,binding):
    api.require(r['input_checkpoint_sha256']==api.digest(before) and r['spec']==spec,'segment binding')
    api.require(r['effective_binding']==model.binding_for(binding,True),'model binding')
    api.require(old.parent.prior.s.check_record(r,before,spec,r['effective_binding'])['passed'],'health/clock/contract')
    api.require(len(r['backend_calls'])==1 and r['backend_calls'][0]['enabled'],'rigid live backend')
    api.require(len(r['rows'])<=r['step_cap']<=2500,'step cap')
    old.parent.segment_guard(r['result'],before,spec['horizon_s'])


def read(p):
    api.require(api.read(p.with_suffix('.seal.json'))=={'record_sha256':api.sha(p),'design_sha256':api.sha(DESIGN)},'new record seal')
    return api.read(p)


def seed_setup(d,wi):
    w=d['windows'][wi];src=api.read(source_path(w,w['source_segment']))
    spec=copy.deepcopy(src['spec']);binding=api.digest([d['binding'],w['id'],'entry'])
    return spec,binding,model.checkpoint(spec,binding,src['result']['checkpoint'],True)


def setup(d,wi,factor,purpose='campaign'):
    w=d['windows'][wi];seed=read(RUN/w['id']/'seed.json')['result']['checkpoint']
    spec=copy.deepcopy(d['base_spec']);spec['horizon_s']=w['horizon_s']
    spec['horizon_pv']=w['horizon_s']*spec['field_metadata']['pv_per_second']
    for k in api.DT_CONTROLS:spec['config']['numerics'][k]*=factor
    binding=api.digest([d['binding'],w['id'],factor,purpose])
    return spec,binding,model.checkpoint(spec,binding,seed,True)


def prepare_seed(d,wi):
    w=d['windows'][wi];folder=RUN/w['id'];folder.mkdir(exist_ok=False)
    spec,binding,cp=seed_setup(d,wi)
    r=execute(d,spec,binding,cp,folder/'seed.json',d['entries'][wi]['steps'])
    expected=api.read(source_path(w,w['next_segment']))['rows'][:d['entries'][wi]['steps']]
    api.require(r['rows']==expected and r['result']['time_s']==d['entries'][wi]['exact_time_s'],'exact archived entry replay')
    api.require((w['grain_id'] in r['rows'][-1]['supported_bearing_ids'])!=w['after_present'],'event already occurred at entry')
    spec,binding,cp=setup(d,wi,FACTORS[-1],'preflight')
    full=execute(d,spec,binding,cp,folder/'preflight_full.json',100)
    first=execute(d,spec,binding,cp,folder/'preflight_first.json',37)
    last=execute(d,spec,binding,first['result']['checkpoint'],folder/'preflight_last.json',63)
    api.require(full['rows']==first['rows']+last['rows'] and full['result']['checkpoint']['state']==last['result']['checkpoint']['state'],'exact refined restart')


def joined(d,wi,factor):
    spec,binding,cp=setup(d,wi,factor);folder=RUN/d['windows'][wi]['id']/f'factor_{factor}'
    paths=sorted(folder.glob('segment_[0-9][0-9].json'));rows=[];cost=0.;certs=[]
    api.require(0<len(paths)<=d['budget']['max_calls_per_level'],'segment count')
    for n,p in enumerate(paths,1):
        api.require(p.name==f'segment_{n:02d}.json','ordered segments');r=read(p);check(r,cp,spec,binding)
        api.require(n==len(paths) or r['result']['status'] in ['paused_checkpoint','incomplete_budget'],'no post-completion run')
        rows+=r['rows'];cost+=r['result']['runtime_seconds'];certs+=r['certificates'];cp=r['result']['checkpoint']
    api.require(r['result']['status']=='present_at_horizon','matched endpoint')
    return {'result':r['result'],'rows':rows,'spec':spec,'cost_s':cost,'certificates':certs}


def impulses(d,wi,recs,field,geometry):
    w=d['windows'][wi];seed=read(RUN/w['id']/'seed.json')['result']['checkpoint']['state']
    cfg=d['base_spec']['config'];a,b,_=cfg['prolate_semiaxes_m'];U=cfg['target_mean_interstitial_velocity_m_s']
    mass,_=diag.backend.generalized_mass_matrix(np.array(seed['p']),a,b,cfg['particle_density_kg_m3'],cfg['fluid_density_kg_m3'],cfg['added_mass_fraction'])
    start,stop=w['impulse_window_s'];levels=[];calls=0
    with old.hot.scope(),engine.runtime.repair_scope(),fix.scope():
        for factor,rec in zip(FACTORS,recs):
            total=np.zeros(6);samples=[]
            for i,row in enumerate(rec['rows']):
                left=seed['t'] if i==0 else rec['rows'][i-1]['time_s'];right=row['time_s']
                overlap=max(0.,min(right,stop)-max(left,start))
                if not overlap:continue
                prev=seed if i==0 else {'x':rec['rows'][i-1]['position_m'],'p':rec['rows'][i-1]['orientation'],
                      'q':rec['rows'][i-1]['velocity_generalized'],'t':left,'recovery':seed['recovery']}
                q,h=diag.replay(field,geometry,rec['spec'],prev,row['dt_s']);calls+=1
                api.require(calls<=d['budget']['max_impulse_replays_per_window'],'impulse replay cap')
                error=float(np.linalg.norm(q-row['velocity_generalized'])/U)
                api.require(error<=1e-8 and h['momentum_residual']<=1e-8 and h['work_balance_relative']<=1e-8,'impulse replay and balance')
                total+=np.array(h['impulse_generalized'])*overlap/row['dt_s']
                samples.append({'time_s':right,'dt_s':row['dt_s'],'overlap_s':overlap,'replay_error_over_U':error,
                                **{k:h[k] for k in ['impulse_generalized','momentum_residual','work_balance_relative']}})
            api.require(abs(sum(x['overlap_s'] for x in samples)-(stop-start))<=1e-13,'full fixed-clock impulse coverage')
            levels.append({'factor':factor,'total_impulse':total.tolist(),'samples':samples})
    compare=lambda x,y:float(np.linalg.norm(np.linalg.solve(mass,np.array(x['total_impulse'])-y['total_impulse']))/U)
    return {'levels':levels,'calls':calls,'to_finest':[compare(x,levels[-1]) for x in levels[:-1]],
            'adjacent':[compare(x,y) for x,y in zip(levels,levels[1:])],
            'mass_at_entry':mass.tolist(),'U':U,'window_s':w['impulse_window_s']}


def summary(d,wi,recs,imp):
    w=d['windows'][wi];seedrec=read(RUN/w['id']/'seed.json');seed=seedrec['result']['checkpoint']
    U=d['base_spec']['config']['target_mean_interstitial_velocity_m_s'];limits=d['accuracy']['limits']
    ratio=d['accuracy']['error_reduction_ratio_max'];noise=d['accuracy']['noise_floor']
    reduced=lambda a,b:b<=ratio*a or max(a,b)<noise
    endpoints=[old.parent.prior.w.compare(a['result'],b['result'],b['spec']) for a,b in zip(recs,recs[1:])]
    traces=[old.parent.prior.common_trace(recs[-1]['rows'],r,seed) for r in recs[:-1]]
    l1=[diag.piecewise_l1(r['rows'],recs[-1]['rows'],seed['state']['t'],w['horizon_s'],U)['mean_norm_over_scale'] for r in recs[:-1]]
    adjacent=[diag.piecewise_l1(a['rows'],b['rows'],seed['state']['t'],w['horizon_s'],U)['mean_norm_over_scale'] for a,b in zip(recs,recs[1:])]
    events=[old.event(r['rows'],seedrec['rows'][-1]['supported_bearing_ids'],seed['state']['t'],w['grain_id'],w['after_present'],d['local_event_persistence_s']) for r in recs]
    spread=max(e['midpoint_s'] for e in events)-min(e['midpoint_s'] for e in events) if all(events) else None
    checks={'endpoints':all(endpoints[-1][k]<=limit and reduced(endpoints[0][k],endpoints[1][k]) for k,limit in limits.items()),
            'whole_pose':all(all(t[k]<=limits[k] for k in ['position_over_b','axis_vector_norm']) for t in traces),
            'whole_L1_velocity':max(l1)<=.005,'L1_refinement':reduced(*adjacent),
            'impulse_accuracy':max(imp['to_finest'])<=.005,'impulse_refinement':reduced(*imp['adjacent']),
            'local_events':spread is not None and spread<=4*max(x['dt_s'] for x in recs[0]['rows'])}
    return {'id':w['id'],'passed':all(checks.values()),'checks':checks,'endpoint_errors':endpoints,'whole_trace_metrics':traces,
            'whole_L1_to_finest':l1,'adjacent_L1':adjacent,'impulse_errors_to_finest':imp['to_finest'],'adjacent_impulse_errors':imp['adjacent'],
            'events':events,'event_spread_s':spread,'entry_s':seed['state']['t'],'horizon_s':w['horizon_s'],
            'cost':[{'factor':f,'steps':len(r['rows']),'runtime_s':r['cost_s'],'exact_certificates':len(r['certificates'])} for f,r in zip(FACTORS,recs)]}


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'design_sha256':api.sha(DESIGN),'python':sys.version})
    old.parent.configure();spec=d['base_spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    reports=[]
    for wi,w in enumerate(d['windows']):
        prepare_seed(d,wi)
        for f in FACTORS:
            spec,binding,cp=setup(d,wi,f);folder=RUN/w['id']/f'factor_{f}';folder.mkdir(exist_ok=False)
            for n in range(1,d['budget']['max_calls_per_level']+1):
                r=execute(d,spec,binding,cp,folder/f'segment_{n:02d}.json',d['budget']['step_cap'])
                if r['result']['status']=='present_at_horizon':break
                cp=r['result']['checkpoint']
            api.require(r['result']['status']=='present_at_horizon','case budget exhausted')
        recs=[joined(d,wi,f) for f in FACTORS];imp=impulses(d,wi,recs,field,geometry)
        report=summary(d,wi,recs,imp);reports.append(report)
        api.write(OUT/f"{w['id']}_impulses.json",imp,raw=True);api.write(OUT/f"{w['id']}_summary.json",report,raw=True)
        print('WINDOW',w['id'],report['checks'],'impulses',imp['to_finest'],flush=True)
        api.require(report['passed'],'local scientific gate failed')
    verify(d)
    result={'stage':'Stage159','passed':True,'windows':reports,'design_sha256':api.sha(DESIGN),
            'artifacts':{str(p):api.sha(p) for folder in [RUN,OUT] for p in folder.rglob('*') if p.is_file()},
            'claim':d['evidence_role'],'full_window_accuracy':False,'production_promotion':False,'prior_failures_unchanged':True}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json'),'passed':True})
    print('STAGE159 PASS',flush=True)


if __name__=='__main__':
    owned=False
    try:
        if sys.argv[1:]==['prepare']:prepare()
        elif sys.argv[1:]==['run']:
            api.require(not RUN.exists() and not OUT.exists(),'immutable destination exists');owned=True;run()
        else:raise ValueError('Use prepare or run')
    except Exception as e:
        if owned and RUN.exists() and not (RUN/'failure.json').exists():api.write(RUN/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()})
        raise
