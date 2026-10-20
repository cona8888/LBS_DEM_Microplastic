"""Three 32-step read-only-input profiling replays, never promoted trajectories."""
from pathlib import Path
import copy,cProfile,pstats,time
import qualify_immutable_field_v1 as unit
api,parent,p,fast=unit.api,unit.parent,unit.p,unit.fast
OUT=unit.OUT.parent/'cached_profile_01'
RUN=unit.RUN.parent/'cached_profile_01'
DESIGN=unit.DESIGN.with_name('profile_design_01.json')


def main():
    unit.prior.unit.check_time();d=api.read(unit.DESIGN);unit.verify(d)
    res=api.read(unit.OUT/'results.json');api.require(res['passed'] and api.read(unit.OUT/'completion.json')['results_sha256']==api.sha(unit.OUT/'results.json'),'snapshot qualified')
    cases=[{**x,'steps':32} for x in d['cases'] if x['id']!='sphere_healthy']
    design={'stage':'Stage173_cached_profile','steps':96,'cases':cases,'sources':parent.source_map(),
            'inputs':{str(x):api.sha(x) for x in [unit.DESIGN,unit.OUT/'results.json',unit.OUT/'completion.json']}}
    design['binding']=api.digest(design);api.write(DESIGN,design);OUT.mkdir(exist_ok=False);RUN.mkdir(exist_ok=False)
    parent.b.old.parent.configure();fast.capture_systems=True;reports=[];artifacts={}
    metadata=parent.storage.read_record(Path(cases[0]['source']),cases[0]['source_design_sha256'])['spec']['field_metadata']
    with unit.snapshot.scope(api,metadata):
        api.fields.load(2,1.,6)
        for case in cases:
            source=parent.storage.read_record(Path(case['source']),case['source_design_sha256']);spec=source['spec'];binding=api.digest([design['binding'],case['id']])
            cp=parent.model.checkpoint(spec,binding,source['result']['checkpoint'],True)
            n0=len(fast.attempts);n1=len(fast.old.telemetry);nc=len(parent.model.calls);nf=len(parent.fix.telemetry)
            profile=cProfile.Profile();started=time.perf_counter()
            with p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),fast.scope(parent.engine.runtime,True):
                profile.enable()
                try:r,rows=parent.engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+32)
                finally:profile.disable()
            rec={'spec':spec,'result':r,'rows':rows,'input_checkpoint_sha256':api.digest(cp),'effective_binding':parent.model.binding_for(binding,True),
                 'design_sha256':api.sha(DESIGN),'step_cap':32,'compute_call_wall_s':time.perf_counter()-started,
                 'early_attempts':copy.deepcopy(fast.attempts[n0:]),'repairs':copy.deepcopy(fast.old.telemetry[n1:]),
                 'backend_calls':copy.deepcopy(parent.model.calls[nc:]),'certificates':copy.deepcopy(parent.fix.telemetry[nf:])}
            path=RUN/(case['id']+'.json.gz');parent.storage.write_record(path,rec);unit.prior.check(rec,cp,binding)
            expected=parent.storage.read_record(unit.RUN/(case['id']+'_cached.json.gz'),api.sha(unit.DESIGN))['rows'][:32]
            api.require(rows==expected and len(rows)==32,'exact profiled trace')
            stats=[{'file':key[0],'line':key[1],'function':key[2],'calls':v[1],'self_s':v[2],'cumulative_s':v[3]} for key,v in pstats.Stats(profile).stats.items()]
            stats.sort(key=lambda x:x['cumulative_s'],reverse=True)
            detail=OUT/(case['id']+'_profile.json');api.write(detail,stats)
            for x in [path,path.with_suffix('.seal.json'),detail]:artifacts[str(x)]=api.sha(x)
            reports.append({'case':case['id'],'exact':True,'steps':32,'profiled_s':rec['compute_call_wall_s'],'top':stats[:30]})
            print('PROFILE',case['id'],'TOP',stats[:12],flush=True)
    api.verify_mapping(design['sources']);api.verify_mapping(design['inputs'])
    result={'passed':True,'new_steps':96,'reports':reports,'artifacts':artifacts,'design_sha256':api.sha(DESIGN),'claim':'Local profile with instrumentation overhead, not a campaign rate.'}
    api.write(OUT/'results.json',result);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':main()
