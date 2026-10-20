"""Bounded new-version integration; no production or failed-run restart."""
from pathlib import Path
import copy, shutil, sys, time, traceback
import numpy as np
import qualify_fast_contact_v1 as unit
api,parent,p,fast=unit.api,unit.parent,unit.p,unit.fast
ROOT=unit.ROOT
DESIGN=unit.CONTRACT.with_name('integration_design_01.json')
RUN=ROOT/'stage172_runs/fast_contact_20260923/preflight_01'
OUT=ROOT/'stage172_evaluations/fast_contact_20260923/integration_01'
TOTAL=0
START=None


def prepare():
    unit.check_time();unit.verify(api.read(unit.DESIGN))
    old=api.read(p.DESIGN);p.verify(old)
    r=api.read(unit.OUT/'results.json')
    api.require(r['passed'] and api.read(unit.OUT/'completion.json')['results_sha256']==api.sha(unit.OUT/'results.json'),'unit seal')
    d=copy.deepcopy(old);d.pop('binding')
    d.update(stage='Stage172_integration',authorization='Four-hour bounded performance engineering; no campaign launch.',
             algorithm='Original physics, stateless early near-rest reduced candidate, otherwise Stage169 qualified stack.',
             stop_utc=api.read(unit.CONTRACT)['end_utc'],sources=parent.source_map())
    for x in [unit.CONTRACT,unit.DESIGN,unit.OUT/'results.json',unit.OUT/'completion.json',p.DESIGN,p.OUT/'results.json',p.OUT/'completion.json']:
        d['inputs'][str(x)]=api.sha(x)
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'integration design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);unit.verify(api.read(unit.DESIGN))


def check(rec,before,binding):
    p.job.check(rec,before,binding)
    api.require(rec['effective_binding']==parent.model.binding_for(binding,True),'effective binding')
    api.require(rec['result']['time_s']<=rec['spec']['horizon_s'],'exact clock bound')
    for row in rec['early_attempts']:
        if not row['accepted']:continue
        h=row['health'];v,M,J,g=[np.asarray(row[k]) for k in ['vfree','mobility','jacobian','gaps_m']]
        q=np.asarray(row['velocity'])
        audit=p.job.unit.independent(v,M,J,g,row['dt_s'],row['friction'],q,h)
        api.require(audit['passed'],'independent early-contact physical gate')
        api.require(h['solver']==fast.NAME and h['original_gaps_preserved'],'qualified new candidate')
        api.require(row['near_rest_ratio']<=1e-4 and np.max(np.abs(g))/row['dt_s']<=1e-5*max(np.linalg.norm(v),1e-15),'stateless dispatch domain')
    api.require(all(x['reduced_accepted'] for x in rec['repairs']),'old fallback certified')


def execute(d,spec,binding,cp,path,cap):
    global TOTAL
    unit.check_time()
    api.require(time.perf_counter()-START<d['budget']['wall_s'],'local wall budget')
    api.require(TOTAL+cap<=d['budget']['maximum_new_steps'],'local step budget')
    api.require(shutil.disk_usage(ROOT).free>=d['budget']['minimum_free_disk_bytes'],'disk reserve')
    before=copy.deepcopy(cp);n0=len(fast.attempts);n1=len(fast.old.telemetry);nc=len(parent.model.calls);nf=len(parent.fix.telemetry)
    started=time.perf_counter()
    with p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),fast.scope(parent.engine.runtime,True):
        result,rows=parent.engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+cap)
    compute_s=time.perf_counter()-started
    rec={'spec':spec,'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(before),
         'effective_binding':parent.model.binding_for(binding,True),'design_sha256':api.sha(DESIGN),'step_cap':cap,
         'repairs':copy.deepcopy(fast.old.telemetry[n1:]),'early_attempts':copy.deepcopy(fast.attempts[n0:]),
         'backend_calls':copy.deepcopy(parent.model.calls[nc:]),'certificates':copy.deepcopy(parent.fix.telemetry[nf:]),
         'compute_call_wall_s':compute_s}
    parent.storage.write_record(path,rec);TOTAL+=len(rows)
    api.require(api.digest(parent.storage.read_record(path,api.sha(DESIGN)))==api.digest(rec),'lossless persisted record')
    check(rec,before,binding)
    print(path.relative_to(RUN),'steps',len(rows),'t',result['time_s'],'early',sum(x['accepted'] for x in rec['early_attempts']),
          'fallback',len(rec['repairs']),'compute_s',round(compute_s,3),flush=True)
    return rec


def run():
    global START
    d=api.read(DESIGN);verify(d);unit.check_time();RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    START=time.perf_counter();parent.b.old.parent.configure();fast.capture_systems=True
    levels=[];identities=[];artifacts={}
    def bind(path):
        for item in [path,path.with_suffix('.seal.json')]:artifacts[str(item)]=api.sha(item)
    try:
        for control in d['controls']:
            source=parent.storage.read_record(Path(control['source']),d['old_source_design_sha256'])
            target=parent.storage.read_record(Path(control['target']),d['old_source_design_sha256'])
            spec=source['spec'];binding=api.digest([d['binding'],control['id']])
            cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True)
            path=RUN/(control['id']+'.json.gz');rec=execute(d,spec,binding,cp,path,control['steps']);bind(path)
            exact=rec['rows']==target['rows'][:control['steps']] and len(rec['rows'])==control['steps']
            api.require(exact,'healthy archived control exact identity')
            identities.append({'id':control['id'],'passed':exact,'steps':len(rec['rows']),'path':str(path)})
        for factor in d['factors_relative_to_old_fine']:
            spec,binding,cp=p.setup(d,factor);seed=copy.deepcopy(cp);rows=[];entries=[];post=[]
            folder=RUN/f'factor_{factor}';folder.mkdir()
            for i in range(d['budget']['maximum_calls_per_level']):
                before_t=cp['state']['t'];path=folder/f'segment_{i+1:03d}.json.gz'
                rec=execute(d,spec,binding,cp,path,d['budget']['step_cap']);bind(path)
                rows.extend(rec['rows']);entries.append({'path':str(path),'sha256':api.sha(path)})
                cp=rec['result']['checkpoint']
                if before_t>=d['failure_time_s']+1e-4 and len(rec['rows'])>=100:
                    post.append({'seconds_per_simulated_second':rec['compute_call_wall_s']/(cp['state']['t']-before_t),
                                 'path':str(path),'steps':len(rec['rows']),'early_accepts':sum(x['accepted'] for x in rec['early_attempts'])})
                if rec['result']['status']=='present_at_horizon':break
            api.require(rec['result']['status']=='present_at_horizon' and cp['state']['t']==d['local_horizon_s'],'exact local observation complete')
            api.require(post,'sustained-contact cost samples')
            levels.append({'factor':factor,'spec':spec,'binding':binding,'seed':seed,'rows':rows,'result':rec['result'],
                           'entries':entries,'post_repair_cost':post})
        lev=levels[1];spec=copy.deepcopy(lev['spec']);spec['horizon_s']+=1e-3
        spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
        binding=api.digest([d['binding'],'early_restart']);cp=parent.model.checkpoint(spec,binding,lev['result']['checkpoint'],True)
        folder=RUN/'restart';folder.mkdir()
        full=execute(d,spec,binding,cp,folder/'full.json.gz',100);bind(folder/'full.json.gz')
        a=execute(d,spec,binding,cp,folder/'first.json.gz',37);bind(folder/'first.json.gz')
        b=execute(d,spec,binding,a['result']['checkpoint'],folder/'last.json.gz',63);bind(folder/'last.json.gz')
        exact=full['rows']==a['rows']+b['rows'] and full['result']['checkpoint']['state']==b['result']['checkpoint']['state']
        api.require(exact and any(x['accepted'] for x in full['early_attempts']),'exact active early dispatch restart')
        metrics=p.comparisons(levels,d)
        # Same-level comparison against the qualified slower Stage171 stack.
        baseline=api.read(p.OUT/'results.json');same=[]
        for level,oldlevel in zip(levels,baseline['levels']):
            oldrows=[]
            for entry in oldlevel['entries']:
                oldrows+=parent.storage.read_record(Path(entry['path']),api.sha(p.DESIGN))['rows']
            pair=[level,{**level,'rows':oldrows,'result':oldlevel['final']}]
            comparison=p.comparisons(pair,d)[0];comparison['factor']=level['factor'];same.append(comparison)
        result={'passed':all(x['passed'] for x in metrics+same),'new_steps':TOTAL,'wall_s':time.perf_counter()-START,
                'identities':identities,'comparisons':metrics,'same_level_slow_stack_comparisons':same,'exact_restart':exact,
                'design_sha256':api.sha(DESIGN),'artifacts':artifacts,'campaign_launched':False,'full_path_qualified':False,
                'levels':[{'factor':x['factor'],'steps':len(x['rows']),'final':x['result'],'entries':x['entries'],
                           'post_repair_cost':x['post_repair_cost']} for x in levels]}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
        print('INTEGRATION',result['passed'],'STEPS',TOTAL,'TIME',result['wall_s'],'METRICS',metrics,'SAME_LEVEL',same,flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'saved_steps':TOTAL,'wall_s':time.perf_counter()-START});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
