"""Immutable snapshot guard tests and exact short trajectory comparisons."""
from pathlib import Path
import copy, cProfile, hashlib, pstats, sys, time, traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage172_staging'))
import integration_fast_contact_v1 as prior
import immutable_field_snapshot_v1 as snapshot
api,parent,p,fast=prior.api,prior.parent,prior.p,prior.fast
DESIGN=ROOT/'stage173_designs/immutable_field_20260923/design_01.json'
RUN=ROOT/'stage173_runs/immutable_field_20260923/qualification_01'
OUT=ROOT/'stage173_evaluations/immutable_field_20260923/qualification_01'


def prepare():
    prior.unit.check_time();prior.verify(api.read(prior.DESIGN))
    r=api.read(prior.OUT.parent/'independent_audit_01/results.json')
    api.require(r['integration_verified'],'qualified fast contact required')
    inherited=api.read(prior.DESIGN);cases=[];inputs=[prior.DESIGN,prior.OUT/'results.json',prior.OUT/'completion.json',
        prior.OUT.parent/'independent_audit_01/results.json',prior.OUT.parent/'independent_audit_01/completion.json']
    for control in inherited['controls']:
        cases.append({'id':control['id'],'source':control['source'],'source_design_sha256':inherited['old_source_design_sha256'],'steps':128})
    cases.append({'id':'sphere_sustained','source':str(prior.RUN/'factor_1.0/segment_007.json.gz'),
                  'source_design_sha256':api.sha(prior.DESIGN),'steps':128})
    for c in cases:
        source=Path(c['source']);inputs.extend([source,source.with_suffix('.seal.json')])
    d={'stage':'Stage173','scope':'Immutable CPD6 data reuse and exact digest certification only; original numerical bytecode unchanged.',
       'physical_changes':[],'trajectory_changes':[],'cases':cases,'required_identity':'bitwise all saved rows and checkpoint state',
       'tests':['immutable bytes owner','write and writable-alias rejection','replaced-array rejection','unsupported domain rejection',
                'full before/after content and dependency hashes','cached versus uncached exact trajectories'],
       'stop_utc':inherited['stop_utc'],'maximum_new_steps':1024,'maximum_wall_s':180.,'workers':1,'threads':1,
       'sources':parent.source_map(),'inputs':{str(x):api.sha(x) for x in inputs}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'snapshot design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);prior.verify(api.read(prior.DESIGN))


def execute(d,c,spec,binding,cp,label,profile=None):
    prior.unit.check_time();n0=len(fast.attempts);n1=len(fast.old.telemetry);nc=len(parent.model.calls);nf=len(parent.fix.telemetry)
    started=time.perf_counter()
    with p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),fast.scope(parent.engine.runtime,True):
        if profile:profile.enable()
        try:r,rows=parent.engine.runtime.execute(spec,binding,checkpoint=copy.deepcopy(cp),pause=cp['state']['steps']+c['steps'])
        finally:
            if profile:profile.disable()
    elapsed=time.perf_counter()-started
    rec={'spec':spec,'result':r,'rows':rows,'input_checkpoint_sha256':api.digest(cp),'effective_binding':parent.model.binding_for(binding,True),
         'design_sha256':api.sha(DESIGN),'step_cap':c['steps'],'compute_call_wall_s':elapsed,'early_attempts':copy.deepcopy(fast.attempts[n0:]),
         'repairs':copy.deepcopy(fast.old.telemetry[n1:]),'backend_calls':copy.deepcopy(parent.model.calls[nc:]),'certificates':copy.deepcopy(parent.fix.telemetry[nf:])}
    path=RUN/(c['id']+'_'+label+'.json.gz');parent.storage.write_record(path,rec);prior.check(rec,cp,binding)
    api.require(len(rows)==c['steps'],'complete bounded probe')
    print(c['id'],label,'steps',len(rows),'wall_s',round(elapsed,5),flush=True)
    return rec,path


def run():
    d=api.read(DESIGN);verify(d);prior.unit.check_time();RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();parent.b.old.parent.configure();fast.capture_systems=True;records=[];pairs=[];guard_tests=[]
    try:
        cases=[];base={}
        for c in d['cases']:
            source=parent.storage.read_record(Path(c['source']),c['source_design_sha256']);spec=source['spec'];binding=api.digest([d['binding'],c['id']])
            cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True);cases.append((c,spec,binding,cp))
            rec,path=execute(d,c,spec,binding,cp,'uncached');records.append(path);base[c['id']]=rec
        metadata=cases[0][1]['field_metadata'];api.require(all(x[1]['field_metadata']==metadata for x in cases),'common frozen field')
        with snapshot.scope(api,metadata) as handle:
            field,geometry,meta=api.fields.load(2,1.,6)
            api.require(meta==metadata,'metadata exact')
            actual=hashlib.sha256(field.u.tobytes()).hexdigest()
            guard_tests.append({'test':'digest_exact','passed':handle['digest'](field)==actual})
            def direct_write():field.u.flat[0]=1.
            def alias_write():field.u.view().setflags(write=True)
            def foreign_array():
                changed=copy.copy(field);changed.u=field.u.copy();handle['digest'](changed)
            def outside_domain():api.fields.load(1,1.,6)
            for name,func in [('direct_write',direct_write),('writable_alias',alias_write),('replaced_array',foreign_array),('other_field',outside_domain)]:
                try:func()
                except (ValueError,RuntimeError):guard_tests.append({'test':name,'passed':True})
                else:guard_tests.append({'test':name,'passed':False})
            api.require(all(x['passed'] for x in guard_tests),'immutable guard tests')
            for c,spec,binding,cp in cases:
                rec,path=execute(d,c,spec,binding,cp,'cached');records.append(path);old=base[c['id']]
                exact=old['rows']==rec['rows'] and old['result']['checkpoint']['state']==rec['result']['checkpoint']['state']
                pairs.append({'case':c['id'],'passed':exact,'steps':len(rec['rows']),'uncached_s':old['compute_call_wall_s'],
                              'cached_s':rec['compute_call_wall_s'],'speedup':old['compute_call_wall_s']/rec['compute_call_wall_s']})
            cache_hashes=copy.deepcopy(handle['cache']['hashes']);generated=handle['generated_source']
        elapsed=time.perf_counter()-start;steps=sum(2*x['steps'] for x in d['cases'])
        api.require(steps<=d['maximum_new_steps'] and elapsed<=d['maximum_wall_s'],'bounded qualification')
        result={'passed':all(x['passed'] for x in guard_tests+pairs),'pairs':pairs,'guards':guard_tests,'new_steps':steps,
                'wall_s':elapsed,'cache_stats':snapshot.stats,'snapshot_hashes':cache_hashes,'full_exit_hashes_passed':True,
                'generated_wrapper_sha256':hashlib.sha256(generated.encode()).hexdigest(),'generated_wrapper_source':generated,
                'design_sha256':api.sha(DESIGN),'artifacts':{str(y):api.sha(y) for x in records for y in [x,x.with_suffix('.seal.json')]},
                'campaign_launched':False,'full_path_qualified':False}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
        print('SNAPSHOT',result['passed'],'PAIRS',pairs,'STEPS',steps,flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
