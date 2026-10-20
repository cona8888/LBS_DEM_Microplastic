"""Versioned 128 vs 64+64 restart test using the qualified same-system solver."""
from pathlib import Path
from datetime import timedelta
import inspect,sys
import numpy as np
import qualify_dispatch_restart_v1 as prior
import semismooth_rejected_seed_v1 as repair
import audit_semismooth_routes_v1 as auditor
q=prior.q;job,api=q.job,q.api;BASE=prior.BASE
DESIGN=prior.DESIGN.with_name('semismooth_restart_01.json')
RUN=prior.RUN.with_name('semismooth_restart_01');OUT=prior.OUT.with_name('semismooth_restart_01')

def prerequisites():
    w,d=prior.prerequisites()
    api.require(job.utc()<job.policy.utc(w['work_end_utc'])-timedelta(seconds=900),'work launch clock')
    for name in ('semismooth_seed_qualification_01','semismooth_outer_qualification_01'):
        r=api.read(BASE/name/'results.json');api.require(r['passed'] and api.read(BASE/name/'completion.json')['results_sha256']==api.sha(BASE/name/'results.json'),'same-system qualification '+name)
    closure=api.read(BASE/'semismooth_outer_qualification_01/qualification_closure.json')
    api.require(closure['passed'] and closure['outer_result_sha256']==api.sha(BASE/'semismooth_outer_qualification_01/results.json'),'outer qualification closure')
    for path in (DESIGN.with_name('semismooth_seed_qualification_01.json'),DESIGN.with_name('semismooth_outer_sources_01.json')):
        p=api.read(path);api.verify_mapping(p['inputs'])
        if 'sources' in p:api.verify_mapping(p['sources'])
    r=api.read(BASE/'dispatch_failure_audit_01/results.json');api.require(r['evidence_audit_passed'] and not r['numerical_campaign_gate_passed'] and r['window_total_new_steps']==19396,'failed attempt included in budget')
    api.require(api.read(BASE/'dispatch_failure_audit_01/completion.json')['results_sha256']==api.sha(BASE/'dispatch_failure_audit_01/results.json'),'independent failed attempt seal')
    api.verify_mapping(api.read(BASE/'dispatch_restart_01/results.json')['artifacts'])
    return w,d

def prefix_comparison(rows,oracle):
    api.require(len(rows)>=55 and len(oracle)==55,'complete 55-step comparator')
    case=api.read(DESIGN)['case'];cfg=case['spec']['config'];b=cfg['prolate_semiaxes_m'][1];U=cfg['target_mean_interstitial_velocity_m_s'];g=api.read(job.DESIGN)['numerical_gates']
    time_difference=max(abs(a['time_s']-b['time_s']) for a,b in zip(rows,oracle))
    api.require(time_difference<=32*np.spacing(oracle[-1]['time_s']),'same physical sample clocks within floating summation resolution')
    position=max(np.linalg.norm(np.asarray(a['position_m'])-b_['position_m'])/b for a,b_ in zip(rows,oracle))
    axis=max(np.linalg.norm(np.asarray(a['orientation'])-b_['orientation']) for a,b_ in zip(rows,oracle))
    velocity=max(np.linalg.norm(np.asarray(a['velocity_generalized'])-b_['velocity_generalized'])/U for a,b_ in zip(rows,oracle))
    passed=position<=g['whole_position_over_b_max'] and axis<=g['whole_axis_vector_norm_max'] and velocity<=g['endpoint_q_over_U_max']
    result={'passed':bool(passed),'rows':55,'exact_rows':rows[:55]==oracle,'max_clock_difference_s':float(time_difference),
       'max_position_over_b':float(position),'max_axis_difference':float(axis),'max_velocity_over_U':float(velocity),
       'gates':g,'claim':'Local overlap with an accepted diagnostic prefix; not fresh selected/fine full-path qualification.'}
    job.commit(OUT/'prefix_comparison.json',result);return passed

namespace={**prior.run.__globals__,'prerequisites':prerequisites,'repair':repair,'auditor':auditor,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,
           'prefix_comparison':prefix_comparison,'__file__':__file__}
prepare_source=inspect.getsource(prior.prepare).replace('19341','19396').replace('19597','19652')
needle="paths+=list(Path(__file__).parent.glob('*.py'))+list(OLD_RUN.glob('*'))"
replacement=needle+"\n    paths += [BASE/n/f for n in ('semismooth_seed_qualification_01','semismooth_outer_qualification_01','dispatch_failure_audit_01','dispatch_restart_01') for f in ('results.json','completion.json')]\n    paths += [BASE/'semismooth_outer_qualification_01/qualification_closure.json',DESIGN.with_name('semismooth_seed_qualification_01.json'),DESIGN.with_name('semismooth_outer_sources_01.json')]"
api.require(prepare_source.count(needle)==1,'exact added qualification input binding');prepare_source=prepare_source.replace(needle,replacement)
prepare_source=prepare_source.replace("'Stage194 bounded fallback dispatch exact restart'","'Stage194 bounded same-system semismooth exact restart'")
run_source=inspect.getsource(prior.run).replace('19341','19396')
edits={"allowed={'diagnostic_replay_01','trajectory_qualification_01'}":"allowed={'diagnostic_replay_01','trajectory_qualification_01','dispatch_restart_01'}",
       "api.require(record['rows'][:55]==oracle['rows'],'exact previously accepted 55-step path')":"api.require(prefix_comparison(record['rows'],oracle['rows']),'original numerical gates on prior accepted local prefix')"}
for a,b in edits.items():api.require(run_source.count(a)==1,'exact versioned diagnostic edit');run_source=run_source.replace(a,b)
exec(compile(prepare_source+'\n'+run_source,str(Path(__file__))+'::bounded_diagnostic_only','exec'),namespace)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:namespace['prepare']()
    elif sys.argv[1:]==['run']:namespace['run']()
    else:raise ValueError('prepare | run')
