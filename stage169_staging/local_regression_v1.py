"""Bounded three-level episode verification, never a campaign continuation."""
from pathlib import Path
import copy,sys,time,traceback
import numpy as np
import verify_reduced_repair_v1 as unit
api,parent,repair,hot=unit.api,unit.parent,unit.repair,unit.hot
DESIGN=unit.DESIGN.with_name('local_protocol_01.json')
OUT=unit.EVAL/'local_evaluation_01'
RUN=unit.RUN
STEP_COUNT=0
START=None


def verify(d):
    unit.verify(api.read(unit.DESIGN))
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'local design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])


def prepare():
    inherited=api.read(unit.DESIGN);unit.verify(inherited)
    units=unit.EVAL/'units_01';r=api.read(units/'results.json')
    api.require(r['passed'] and api.read(units/'completion.json')['results_sha256']==api.sha(units/'results.json'),'units qualified')
    api.verify_mapping(r['artifacts'])
    d={'stage':'Stage169_local','upstream_design_sha256':api.sha(unit.DESIGN),'budget':inherited['budget'],'limits':inherited['limits'],
        'factors':inherited['factors_relative_to_stage167_fine'],'horizon_s':inherited['local_horizon_s'],
        'source_checkpoint':inherited['source_checkpoint'],'failed_segment':inherited['failed_segment'],
        'fixed_stop':'600-second local wall ceiling, 25,000 accepted test steps, three levels only. No long trajectories.',
        'restart_lengths':[100,37,63],'sources':parent.source_map(),
        'inputs':{str(p):api.sha(p) for p in [unit.DESIGN,units/'results.json',units/'completion.json']}}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('LOCAL FROZEN',api.sha(DESIGN),flush=True)


def setup(d,factor,purpose='level'):
    source=parent.storage.read_record(Path(d['source_checkpoint']),api.sha(parent.DESIGN))
    spec=copy.deepcopy(source['spec']);spec['horizon_s']=d['horizon_s'];spec['horizon_pv']=d['horizon_s']*spec['field_metadata']['pv_per_second']
    for key in api.DT_CONTROLS:spec['config']['numerics'][key]*=factor
    binding=api.digest([d['binding'],factor,purpose])
    cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True)
    return spec,binding,cp


def check(rec,before,binding):
    r=rec['result'];spec=rec['spec'];state=r['checkpoint']['state'];rows=rec['rows']
    api.require(rec['input_checkpoint_sha256']==api.digest(before),'checkpoint input')
    api.require(r['checkpoint']['state_sha256']==api.digest(state),'checkpoint state')
    api.require(r['checkpoint']['contract']==parent.engine.prior.contracts.expected_contract(spec,parent.model.binding_for(binding,True)),'contract')
    api.require(r['rejected']==before['state']['rejected'],'no new rejected trials')
    api.require(parent.engine.prior.reference.independent_health(r,spec)['passed'],'independent health')
    api.require(parent.b.old.parent.prior.w.prior.audit.clock_chain(before['state']['t'],rows,r['time_s'])['passed'],'accepted clock')
    api.require(r['status'] in ['present_at_horizon','paused_checkpoint','incomplete_budget'],'healthy completion/status')
    api.require(0<len(rows)==r['steps']-before['state']['steps']<=rec['step_cap'],'step accounting')
    api.require(rows[-1]['position_m']==state['x'] and rows[-1]['velocity_generalized']==state['q'],'final row binding')
    api.require(np.allclose(rows[-1]['orientation'],state['p'],rtol=0,atol=1e-12),'axis binding')
    api.require(all(x['accepted'] and x['health']['solver']==repair.NAME for x in r['stage119_repair_calls']),'only new verified fallback accepted')
    api.require(len(rec['backend_calls'])==1 and rec['backend_calls'][0]['enabled'],'one bound rigid backend')


def execute(d,spec,binding,cp,path,cap):
    global STEP_COUNT
    api.require(time.perf_counter()-START<d['budget']['wall_seconds_local'],'local wall budget')
    api.require(STEP_COUNT+cap<=d['budget']['maximum_total_local_steps'],'local total step budget')
    before=copy.deepcopy(cp);n=len(repair.telemetry);nc=len(parent.model.calls)
    with hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),repair.scope(parent.engine.runtime,True):
        r,rows=parent.engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+cap)
    rec={'spec':spec,'result':r,'rows':rows,'input_checkpoint_sha256':api.digest(before),'effective_binding':parent.model.binding_for(binding,True),
        'design_sha256':api.sha(DESIGN),'step_cap':cap,'repairs':copy.deepcopy(repair.telemetry[n:]),'backend_calls':copy.deepcopy(parent.model.calls[nc:])}
    parent.storage.write_record(path,rec);STEP_COUNT+=len(rows)
    api.require(api.digest(parent.storage.read_record(path,api.sha(DESIGN)))==api.digest(rec),'lossless raw')
    check(rec,before,binding)
    print(path.relative_to(RUN),r['status'],'steps',len(rows),'t',r['time_s'],'repairs',len(rec['repairs']),flush=True)
    return rec


def run():
    global START
    d=api.read(DESIGN);verify(d);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(exist_ok=False);START=time.perf_counter()
    parent.b.old.parent.configure();levels=[];restart={};first_level_records=[]
    try:
        for fi,factor in enumerate(d['factors']):
            folder=RUN/f'factor_{factor}';folder.mkdir()
            spec,binding,cp=setup(d,factor);seed=copy.deepcopy(cp);rows=[];entries=[]
            for i in range(d['budget']['maximum_calls_per_level']):
                path=folder/f'segment_{i+1:03d}.json.gz'
                rec=execute(d,spec,binding,cp,path,d['budget']['step_cap_per_call'])
                if fi==0:first_level_records.append((copy.deepcopy(cp),path,rec))
                rows.extend(rec['rows']);entries.append({'path':str(path),'sha256':api.sha(path)})
                cp=rec['result']['checkpoint']
                if rec['result']['status']=='present_at_horizon':break
            api.require(rec['result']['status']=='present_at_horizon' and cp['state']['t']==d['horizon_s'],'complete local horizon')
            levels.append({'factor':factor,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':rec['result'],'entries':entries})
        # Verify prefix unaffected, then split directly across the corrected event.
        old=parent.storage.read_record(Path(d['failed_segment']),api.sha(parent.DESIGN))
        first=old['result']['rejected_trials'][0]['time_s']
        expected=[r for r in old['rows'] if r['time_s']<=first]
        api.require(levels[0]['rows'][:len(expected)]==expected,'exact unchanged pre-failure prefix')
        target_step=levels[0]['seed']['state']['steps']+len(expected)-10
        candidates=[x for x in first_level_records if x[0]['state']['steps']<=target_step]
        before,path,_=candidates[-1]
        folder=RUN/'restart';folder.mkdir();spec=levels[0]['spec'];binding=levels[0]['binding']
        cap=target_step-before['state']['steps']
        entry=execute(d,spec,binding,before,folder/'entry.json.gz',cap)['result']['checkpoint'] if cap else before
        full=execute(d,spec,binding,entry,folder/'full.json.gz',100)
        a=execute(d,spec,binding,entry,folder/'first.json.gz',37)
        b=execute(d,spec,binding,a['result']['checkpoint'],folder/'last.json.gz',63)
        restart={'exact_rows':full['rows']==a['rows']+b['rows'],
                 'exact_checkpoint_state':full['result']['checkpoint']['state']==b['result']['checkpoint']['state'],
                 'crossed_corrected_event':len(full['repairs'])>0,'unchanged_prefix_steps':len(expected)}
        api.require(all(v for k,v in restart.items() if k!='unchanged_prefix_steps'),'exact repair restart')
        # Nodal pose interpolation and exact piecewise-constant velocity L1.
        reference=levels[-1];comparisons=[];seed=reference['seed']['state'];start=seed['t']
        a,bminor,_=reference['spec']['config']['prolate_semiaxes_m'];U=reference['spec']['config']['target_mean_interstitial_velocity_m_s']
        def series(level,key,start_value):
            times=np.r_[start,[row['time_s'] for row in level['rows']]]
            values=np.vstack([start_value,[row[key] for row in level['rows']]])
            return times,values
        for level in levels[:-1]:
            numbers={}
            for key,state_key,scale,label in [('position_m','x',bminor,'pose_b'),('orientation','p',1.,'axis')]:
                ta,va=series(level,key,seed[state_key]);tb,vb=series(reference,key,seed[state_key]);ts=np.union1d(ta,tb)
                pa=np.column_stack([np.interp(ts,ta,va[:,k]) for k in range(3)])
                pb=np.column_stack([np.interp(ts,tb,vb[:,k]) for k in range(3)])
                numbers[label]=float(np.max(np.linalg.norm(pa-pb,axis=1))/scale)
            numbers['endpoint_velocity_U']=float(np.linalg.norm(np.asarray(level['result']['velocity_generalized'])-reference['result']['velocity_generalized'])/U)
            numbers['mean_L1_velocity_U']=parent.b.q.diag.piecewise_l1(level['rows'],reference['rows'],start,d['horizon_s'],U)['mean_norm_over_scale']
            checks={key:value<=d['limits'][key] for key,value in numbers.items()}
            comparisons.append({'factor':level['factor'],'metrics':numbers,'checks':checks,'passed':all(checks.values())})
        result={'passed':all(x['passed'] for x in comparisons),'restart':restart,'comparisons':comparisons,'total_new_steps':STEP_COUNT,
            'levels':[{'factor':x['factor'],'steps':len(x['rows']),'final':x['result'],'entries':x['entries']} for x in levels],
            'wall_s':time.perf_counter()-START,'design_sha256':api.sha(DESIGN),'claim':'Local episode verification only; not full-path accuracy or campaign qualification.'}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
        print('LOCAL_RESULT',result['passed'],'STEPS',STEP_COUNT,'COMPARISONS',comparisons,flush=True)
    except Exception as error:
        api.write(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'steps_saved':STEP_COUNT,'wall_s':time.perf_counter()-START})
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare or run')
