"""Qualify explicit resource deadlines without changing contact physics.

Six 1,000-step archived restart oracles; no production or full-path advance.
"""
from pathlib import Path
from types import SimpleNamespace
import copy,datetime,os,shutil,sys,time,traceback
import explicit_runtime_deadline_v1 as candidate
ROOT=candidate.ROOT
sys.path[:0]=[str(ROOT/'stage177_staging'),str(ROOT/'stage180_staging'),str(ROOT/'stage179_staging')]
import extended_optimized_preflight_v1 as prior
import audit_extended_preflight_v1 as independent
import audit_optimized_record_v1 as audit
import lossless_history_prefix_v1 as codec
api,parent,fast=prior.api,prior.parent,prior.fast
CONTRACT=ROOT/'stage172_designs/four_hour_work_20260923/contract_01.json'
DESIGN=ROOT/'stage181_designs/explicit_resource_deadline_20260924/design_01.json'
RUN=ROOT/'stage181_runs/explicit_resource_deadline_20260924/qualification_01'
OUT=ROOT/'stage181_evaluations/explicit_resource_deadline_20260924/qualification_01'


def prepare():
    prior.verify(api.read(prior.DESIGN));work=api.read(CONTRACT);cases=[]
    inputs=[CONTRACT,prior.DESIGN,independent.OUT/'results.json',independent.OUT/'completion.json']
    for c in api.read(prior.DESIGN)['cases']:
        source=prior.RUN/c['id']/'segment_002.json.xz';oracle=source.with_name('restart_full.json.xz')
        cases.append({'id':c['id'],'spec':c['spec'],'source':str(source),'oracle':str(oracle)})
        inputs.extend([source,source.with_suffix('.seal.json'),oracle,oracle.with_suffix('.seal.json')])
    d={'stage':'Stage181 explicit resource deadline','deadline_utc':work['end_utc'],'cases':cases,
       'physical_changes':[],'new_steps_maximum':6000,'steps_per_case':1000,'prior_work_steps':201175,
       'work_step_ceiling':work['resources']['max_total_new_trajectory_steps'],'workers':1,'threads':1,'wall_seconds':900,
       'source_raw_design_sha256':api.sha(prior.DESIGN),'sources':parent.source_map(),'inputs':{str(p):api.sha(p) for p in inputs},
       'minimum_gap_semantics':api.read(prior.DESIGN)['minimum_gap_semantics'],
       'claim':'Resource timestamp namespace only. Current four-hour cutoff enforced; future campaign still requires separate authority and guards.'}
    api.require(d['prior_work_steps']+d['new_steps_maximum']<=d['work_step_ceiling'],'trajectory allowance')
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);prior.verify(api.read(prior.DESIGN))


def unit_tests(deadline):
    identity=candidate.structural_identity(deadline)
    api.require(identity['same_code_object'] and identity['same_defaults'] and identity['same_closure'] and identity['namespace_differences']==['END_UTC'],'identical generator and only timestamp namespace replacement')
    guards=[];old_deadline=fast.END_UTC;calls=[]
    def primary(*args):calls.append('primary');return np.zeros(6),{'test_only':True}
    def mixed(*args):calls.append('mixed');return np.zeros(6),{'test_only':True}
    mock=SimpleNamespace(probe=SimpleNamespace(RECOVERY=SimpleNamespace(portfolio=SimpleNamespace(_solve=primary))),mixed=SimpleNamespace(solve=mixed))
    def reject(name,fn):
        try:fn()
        except (ValueError,RuntimeError,TypeError):guards.append(name);return
        raise AssertionError('guard accepted '+name)
    for value in [None,True,1.,'2026-09-24T02:46:55','2026-09-24T03:46:55+01:00','not-a-time']:
        reject('invalid_deadline_'+repr(value),lambda value=value:candidate.parse_deadline(value))
    def enter_expired():
        with candidate.scope(mock,'2000-01-01T00:00:00Z',True):raise AssertionError('expired entry')
    reject('expired_entry',enter_expired)
    with candidate.scope(mock,deadline,True):
        outer=mock.probe.RECOVERY.portfolio._solve;outer_mixed=mock.mixed.solve
        with candidate.scope(mock,deadline,True):
            api.require(mock.probe.RECOVERY.portfolio._solve is not outer,'separate nested wrapper')
        api.require(mock.probe.RECOVERY.portfolio._solve is outer and mock.mixed.solve is outer_mixed,'nested restoration')
    api.require(mock.probe.RECOVERY.portfolio._solve is primary and mock.mixed.solve is mixed,'original functions restored')
    # A copied namespace with a test-only clock exercises expiry AFTER entry.
    generated=candidate.bind_scope(deadline).__wrapped__
    generated.__globals__['time']=SimpleNamespace(time=lambda:candidate.parse_deadline(deadline)+1.)
    from contextlib import contextmanager
    args=(np.zeros(6),np.eye(6),np.zeros((0,6)),np.zeros(0),1.,.3,1e-10,1)
    def inner_expiry():
        with contextmanager(generated)(mock,True):mock.probe.RECOVERY.portfolio._solve(*args)
    reject('expiry_inside_contact',inner_expiry)
    api.require(not calls and fast.END_UTC==old_deadline and mock.probe.RECOVERY.portfolio._solve is primary and mock.mixed.solve is mixed,'no fallback bypass or global mutation on expiry')
    with candidate.scope(mock,deadline,False):api.require(mock.probe.RECOVERY.portfolio._solve is primary and mock.mixed.solve is mixed,'disabled identity')
    return {'structural_identity':identity,'guard_rejections':guards,'nested_restoration':True,'disabled_identity':True,'new_trajectory_steps':0}


def run():
    d=api.read(DESIGN);verify(d);api.require(time.time()<candidate.parse_deadline(d['deadline_utc'])-120,'bounded audit reserve')
    RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);start=time.perf_counter();total=0;rows=[];artifacts={}
    api.write(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'design_sha256':api.sha(DESIGN)})
    try:
        units=unit_tests(d['deadline_utc']);parent.b.old.parent.configure();fast.capture_systems=True
        with prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            field,data,meta=api.fields.load(2,1.,6);geometry=prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            for c in d['cases']:
                api.require(time.perf_counter()-start<d['wall_seconds'] and time.time()<candidate.parse_deadline(d['deadline_utc'])-120,'bounded runtime')
                api.require(shutil.disk_usage(ROOT).free>20*1024**3+codec.base.MAX_COMPRESSED,'disk reserve')
                source=independent.independent_read(c['source'],d['source_raw_design_sha256']);oracle=independent.independent_read(c['oracle'],d['source_raw_design_sha256'])
                binding=api.digest([d['binding'],c['id']]);cp=parent.model.checkpoint(c['spec'],binding,source['result']['checkpoint'],True);before=copy.deepcopy(cp);t=time.perf_counter()
                with prior.p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),candidate.scope(parent.engine.runtime,d['deadline_utc'],True),prior.candidate.scope():
                    result,trace=parent.engine.runtime.execute(c['spec'],binding,checkpoint=cp,pause=cp['state']['steps']+d['steps_per_case'])
                record={'spec':c['spec'],'result':result,'rows':trace,'input_checkpoint_sha256':api.digest(before),'effective_binding':parent.model.binding_for(binding,True),
                        'design_sha256':api.sha(DESIGN),'step_cap':d['steps_per_case'],'compute_call_wall_s':time.perf_counter()-t,
                        'early_attempts':copy.deepcopy(fast.attempts),'repairs':copy.deepcopy(fast.old.telemetry),'backend_calls':copy.deepcopy(parent.model.calls),
                        'certificates':copy.deepcopy(parent.fix.telemetry),'sweep_certificates':copy.deepcopy(prior.candidate.records),'minimum_gap_semantics':d['minimum_gap_semantics']}
                path=RUN/(c['id']+'.json.xz');codec.write_record(path,record);total+=len(trace)
                api.require(total<=d['new_steps_maximum'] and len(trace)==d['steps_per_case'],'new step accounting')
                api.require(trace==oracle['rows'] and result['checkpoint']['state']==oracle['result']['checkpoint']['state'],'bitwise archived trace and full state identity')
                decoded,_=codec.read_record(path,api.sha(DESIGN));summary=audit.evaluate(decoded,c['spec'],binding,before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])
                rows.append({'case':c['id'],'steps':len(trace),'exact_trace':True,'exact_state':True,'audit':summary,'path':str(path)})
                for p in [path,path.with_suffix('.seal.json')]:artifacts[str(p)]=api.sha(p)
                fast.attempts.clear();fast.telemetry.clear();fast.old.telemetry.clear();parent.model.calls.clear();parent.fix.telemetry.clear();prior.candidate.records.clear()
                print('DEADLINE_IDENTITY',c['id'],len(trace),flush=True)
        verify(d);api.verify_mapping(artifacts);report={'passed':True,'cases':rows,'units':units,'new_steps':total,'work_cumulative_steps':total+d['prior_work_steps'],
            'wall_seconds':time.perf_counter()-start,'artifacts':artifacts,'design_sha256':api.sha(DESIGN),'campaign_launched':False,'claim':d['claim']}
        api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('DEADLINE_QUALIFIED',total,flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_steps':total});raise


import numpy as np
if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
