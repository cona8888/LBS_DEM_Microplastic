"""1,024 serial versus 512+512 early-dispatch steps, reserving 2,048 total."""
from pathlib import Path
import sys,types
import qualify_semismooth_restart_v1 as old
import early_semismooth_dispatch_v1 as repair
import audit_early_semismooth_v1 as auditor
q=old.q;job,api=q.job,q.api;BASE=old.BASE
DESIGN=old.DESIGN.with_name('early_semismooth_restart_01.json');RUN=old.RUN.with_name('early_semismooth_restart_01');OUT=old.OUT.with_name('early_semismooth_restart_01')

def prerequisites():
    w,d=old.prerequisites()
    r=api.read(BASE/'semismooth_restart_01/results.json');api.require(r['passed'] and r['exact_restart'] and r['window_total_new_steps']==19652,'resolved exact restart ledger')
    api.require(api.read(BASE/'semismooth_restart_01/completion.json')['results_sha256']==api.sha(BASE/'semismooth_restart_01/results.json'),'restart seal');api.verify_mapping(r['artifacts'])
    p=api.read(old.DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    r=api.read(BASE/'early_semismooth_qualification_01/results.json');api.require(r['passed'] and r['outer_exact']==136 and r['controls_exact']==75,'early exact fixed-pose qualification')
    api.require(api.read(BASE/'early_semismooth_qualification_01/completion.json')['results_sha256']==api.sha(BASE/'early_semismooth_qualification_01/results.json'),'early qualification seal');api.verify_mapping(r['artifacts'])
    p=api.read(DESIGN.with_name('early_semismooth_qualification_01.json'));api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    return w,d

prefix_old=types.FunctionType(old.prefix_comparison.__code__,{**old.prefix_comparison.__globals__,'DESIGN':DESIGN,'OUT':OUT},'prefix_comparison',old.prefix_comparison.__defaults__,old.prefix_comparison.__closure__)
def prefix_comparison(rows,oracle):
    passed=prefix_old(rows,oracle)
    reference=q.independent_file(old.RUN/'call_01.json.xz',api.sha(old.DESIGN))
    api.require(rows[:128]==reference['rows'],'exact prior 128-step trajectory under early dispatch')
    job.commit(OUT/'exact_128_prefix.json',{'passed':True,'source_raw_sha256':api.sha(old.RUN/'call_01.json.xz'),'compared_rows':128,'new_trajectory_steps':0})
    return passed

ns={**old.namespace,'prerequisites':prerequisites,'repair':repair,'auditor':auditor,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'prefix_comparison':prefix_comparison,'__file__':__file__}
prepare_source=old.prepare_source.replace('19652','21700').replace('19396','19652').replace('[128,64,64]','[1024,512,512]').replace('256','2048')
needle="p={'stage':"
insert="paths += [BASE/n/f for n in ('early_semismooth_qualification_01','semismooth_restart_01') for f in ('results.json','completion.json')]\n    paths += [DESIGN.with_name('early_semismooth_qualification_01.json'),DESIGN.with_name('semismooth_restart_01.json')]\n    "+needle
api.require(prepare_source.count(needle)==1,'bind new early and restart qualification');prepare_source=prepare_source.replace(needle,insert)
prepare_source=prepare_source.replace('Stage194 bounded same-system semismooth exact restart','Stage194 original near-rest early dispatch exact restart')
run_source=old.run_source.replace('19396','19652').replace('256','2048')
needle="allowed={'diagnostic_replay_01','trajectory_qualification_01','dispatch_restart_01'}"
api.require(run_source.count(needle)==1,'include resolved previous ledger');run_source=run_source.replace(needle,"allowed={'diagnostic_replay_01','trajectory_qualification_01','dispatch_restart_01','semismooth_restart_01'}")
exec(compile(prepare_source+'\n'+run_source,str(Path(__file__))+'::bounded_diagnostic_only','exec'),ns)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:ns['prepare']()
    elif sys.argv[1:]==['run']:ns['run']()
    else:raise ValueError('prepare | run')
