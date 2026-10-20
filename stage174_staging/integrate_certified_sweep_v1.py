"""Paired old/new fibre trajectories at three fixed timestep levels."""
from pathlib import Path
from contextlib import nullcontext
import copy,sys,time,traceback
import numpy as np
import qualify_certified_sweep_v2 as qualification
unit=qualification.job
api,parent,p,fast=unit.api,unit.parent,unit.p,unit.fast
snapshot=unit.upstream.snapshot
candidate=unit.candidate
ROOT=unit.ROOT
DESIGN=unit.DESIGN.with_name('integration_design_01.json')
RUN=ROOT/'stage174_runs/certified_sweep_20260924/paired_01'
OUT=ROOT/'stage174_evaluations/certified_sweep_20260924/integration_01'
TOTAL=0
START=None


def prepare():
    unit.upstream.prior.unit.check_time();d0=api.read(unit.DESIGN);unit.verify(d0)
    r=api.read(unit.OUT/'results.json');api.require(r['passed'] and api.read(unit.OUT/'completion.json')['results_sha256']==api.sha(unit.OUT/'results.json'),'geometric qualification seal')
    source=next(x for x in d0['cases'] if x['id']=='fibre_fine_healthy')
    raw=parent.storage.read_record(Path(source['source']),source['source_design_sha256'])
    inputs=[unit.DESIGN,unit.OUT/'results.json',unit.OUT/'completion.json',Path(source['source']),Path(source['source']).with_suffix('.seal.json')]
    d={'stage':'Stage174_paired_integration','physical_changes':[],'source':source,
       'factors_relative_to_old_fine':[2.,1.,.5],'horizon_s':raw['result']['time_s']+.0015,
       'limits':api.read(unit.upstream.prior.DESIGN)['limits'],'diagnostic_semantics':d0['diagnostic_semantics'],
       'identity_exceptions':['checkpoint.state.minimum_gap','checkpoint.state.history[*][13]'],
       'budget':{'maximum_new_steps':50000,'wall_s':900.,'step_cap':500,'maximum_calls_per_level':30,'workers':1,'threads':1,'minimum_free_disk_bytes':20*1024**3},
       'stop_utc':d0['stop_utc'],'sources':parent.source_map(),'inputs':{str(x):api.sha(x) for x in inputs}}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'paired integration binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);unit.verify(api.read(unit.DESIGN))


def physical_state(state):
    s=copy.deepcopy(state);s.pop('minimum_gap')
    for row in s['history']:row[13]=None
    return s


def setup(d,factor,variant):
    source=parent.storage.read_record(Path(d['source']['source']),d['source']['source_design_sha256'])
    spec=copy.deepcopy(source['spec']);spec['horizon_s']=d['horizon_s'];spec['horizon_pv']=d['horizon_s']*spec['field_metadata']['pv_per_second']
    for key in api.DT_CONTROLS:spec['config']['numerics'][key]*=factor
    binding=api.digest([d['binding'],factor,variant]);cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True)
    return spec,binding,cp


def execute(d,spec,binding,cp,path,cap,enabled):
    global TOTAL
    unit.upstream.prior.unit.check_time()
    api.require(time.perf_counter()-START<d['budget']['wall_s'] and TOTAL+cap<=d['budget']['maximum_new_steps'],'bounded paired execution')
    n0=len(fast.attempts);n1=len(fast.old.telemetry);nc=len(parent.model.calls);nf=len(parent.fix.telemetry);ng=len(candidate.records)
    started=time.perf_counter()
    with p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),fast.scope(parent.engine.runtime,True),candidate.scope() if enabled else nullcontext():
        result,rows=parent.engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+cap)
    elapsed=time.perf_counter()-started
    rec={'spec':spec,'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(cp),'effective_binding':parent.model.binding_for(binding,True),
         'design_sha256':api.sha(DESIGN),'step_cap':cap,'compute_call_wall_s':elapsed,
         'early_attempts':copy.deepcopy(fast.attempts[n0:]),'repairs':copy.deepcopy(fast.old.telemetry[n1:]),
         'backend_calls':copy.deepcopy(parent.model.calls[nc:]),'certificates':copy.deepcopy(parent.fix.telemetry[nf:]),
         'sweep_certificates':copy.deepcopy(candidate.records[ng:]),'certified_sweep_enabled':enabled,
         'minimum_gap_semantics':'conservative_lower_bound' if enabled else 'legacy_bounded_minimum_estimate'}
    parent.storage.write_record(path,rec);TOTAL+=len(rows);unit.upstream.prior.check(rec,cp,binding)
    if enabled:
        api.require(len(rec['sweep_certificates'])==len(rows),'one sweep record per accepted step with no rejection')
        api.require(all(not x['certified'] or x['lower_bound_m']>=x['threshold_m'] for x in rec['sweep_certificates']),'unchanged penetration threshold')
    print(path.relative_to(RUN),'steps',len(rows),'t',result['time_s'],'compute',round(elapsed,4),flush=True)
    return rec


def run():
    global START
    d=api.read(DESIGN);verify(d);unit.upstream.prior.unit.check_time();RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    START=time.perf_counter();parent.b.old.parent.configure();fast.capture_systems=True;levels=[];pairs=[];artifacts={}
    def bind(path):
        for x in [path,path.with_suffix('.seal.json')]:artifacts[str(x)]=api.sha(x)
    try:
        metadata=setup(d,1.,'old')[0]['field_metadata']
        with snapshot.scope(api,metadata):
            api.fields.load(2,1.,6)
            for factor in d['factors_relative_to_old_fine']:
                pair=[]
                for variant in ['old','certificate']:
                    spec,binding,cp=setup(d,factor,variant);seed=copy.deepcopy(cp);rows=[];entries=[];timings=[];proofs=0
                    folder=RUN/f'factor_{factor}'/variant;folder.mkdir(parents=True)
                    for i in range(d['budget']['maximum_calls_per_level']):
                        path=folder/f'segment_{i+1:03d}.json.gz';before=cp['state']['t']
                        rec=execute(d,spec,binding,cp,path,d['budget']['step_cap'],variant=='certificate');bind(path)
                        cp=rec['result']['checkpoint'];rows+=rec['rows'];entries.append(str(path))
                        timings.append({'steps':len(rec['rows']),'wall_s':rec['compute_call_wall_s'],'simulated_s':cp['state']['t']-before,
                                        'rate_s_per_sim_s':rec['compute_call_wall_s']/(cp['state']['t']-before),'path':str(path)})
                        proofs+=sum(x['certified'] for x in rec['sweep_certificates'])
                        if rec['result']['status']=='present_at_horizon':break
                    api.require(rec['result']['status']=='present_at_horizon' and cp['state']['t']==d['horizon_s'],'exact paired endpoint')
                    pair.append({'factor':factor,'variant':variant,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':rec['result'],
                                 'entries':entries,'timings':timings,'proofs':proofs})
                exact=pair[0]['rows']==pair[1]['rows'] and physical_state(pair[0]['result']['checkpoint']['state'])==physical_state(pair[1]['result']['checkpoint']['state'])
                api.require(exact and pair[1]['proofs']>0,'exact physical trajectory; lower-bound diagnostic only')
                pairs.append({'factor':factor,'passed':exact,'steps_per_variant':len(pair[0]['rows']),'certified_steps':pair[1]['proofs'],
                              'old_compute_s':sum(x['wall_s'] for x in pair[0]['timings']),'new_compute_s':sum(x['wall_s'] for x in pair[1]['timings'])})
                levels+=pair
            level=next(x for x in levels if x['factor']==1. and x['variant']=='certificate')
            spec=copy.deepcopy(level['spec']);spec['horizon_s']+=.001;spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
            binding=api.digest([d['binding'],'restart']);cp=parent.model.checkpoint(spec,binding,level['result']['checkpoint'],True)
            folder=RUN/'restart';folder.mkdir()
            full=execute(d,spec,binding,cp,folder/'full.json.gz',100,True);bind(folder/'full.json.gz')
            a=execute(d,spec,binding,cp,folder/'first.json.gz',37,True);bind(folder/'first.json.gz')
            b=execute(d,spec,binding,a['result']['checkpoint'],folder/'last.json.gz',63,True);bind(folder/'last.json.gz')
            exact_restart=full['rows']==a['rows']+b['rows'] and full['result']['checkpoint']['state']==b['result']['checkpoint']['state']
            api.require(exact_restart and any(x['certified'] for x in full['sweep_certificates']),'exact certified restart')
        selected=[x for x in levels if x['variant']=='certificate'];compare_d={**d,'local_horizon_s':d['horizon_s']}
        comparisons=p.comparisons(selected,compare_d)
        result={'passed':all(x['passed'] for x in comparisons+pairs),'new_steps':TOTAL,'wall_s':time.perf_counter()-START,
                'pairs':pairs,'comparisons':comparisons,'exact_restart':exact_restart,'minimum_gap_semantics':d['diagnostic_semantics'],
                'levels':[{k:x[k] for k in ['factor','variant','spec','binding','seed','result','entries','timings','proofs']} for x in levels],
                'artifacts':artifacts,'design_sha256':api.sha(DESIGN),'campaign_launched':False,'full_path_qualified':False}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
        print('SWEEP_INTEGRATION',result['passed'],'PAIRS',pairs,'METRICS',comparisons,'STEPS',TOTAL,flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'saved_steps':TOTAL,'wall_s':time.perf_counter()-START});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
