"""Independent read-only recomputation of completion, gates and restart links."""
import copy
from pathlib import Path
import verify_modal_dt_v1 as job

api=job.api
OUT=job.OUT.parent/'independent_audit_01'


def sealed(folder):
    result=api.read(folder/'results.json');seal=api.read(folder/'completion.json')
    api.require(result['passed'] and seal['passed'] and api.sha(folder/'results.json')==seal['results_sha256'],'passed evaluation seal')
    api.verify_mapping(result['artifacts'])
    return result


def main():
    d=api.read(job.DESIGN);job.verify(d)
    previous=sealed(job.s.OUT);result=sealed(job.OUT)
    api.require(not list(job.RUN.rglob('failure.json')) and not list(job.s.RUN.rglob('failure.json')),'no new failure markers')
    job.w.prior.parent.old.prior.prior.configure()
    old=api.read(job.w.DESIGN);source=api.read(old['case']['source'])['result']['checkpoint']
    original_spec=old['case']['spec'];records=[];checks=[]
    for factor in d['factors']:
        rec=api.read(job.RUN/f'factor_{factor}.json');spec=copy.deepcopy(original_spec)
        spec['horizon_s']=source['state']['t']+old['moving']['window_s'];spec['horizon_pv']=spec['horizon_s']*spec['field_metadata']['pv_per_second']
        for key in api.DT_CONTROLS:spec['config']['numerics'][key]*=factor
        api.require(spec==rec['spec'],'expected unchanged physical spec')
        binding=api.digest([d['binding'],'paired_rotational_modes',factor]);effective=job.model.binding_for(binding,True)
        cp=job.model.checkpoint(spec,binding,source,True)
        check=job.s.check_record(rec,cp,spec,effective)
        api.require(check['passed'] and rec['result']['status']=='present_at_horizon' and rec['result']['time_s']==spec['horizon_s'],'recomputed full completion')
        checks.append({'factor':factor,'independent_health_passed':True,'exact_clock_passed':True,'steps':len(rec['rows']),
                       'new_rejections':rec['result']['rejected']-source['state']['rejected']})
        records.append(rec)
    errors=[job.w.compare(a['result'],b['result'],b['spec']) for a,b in zip(records,records[1:])]
    api.require(errors==result['comparison']['three_level_errors'],'recomputed endpoint differences')
    archived=api.read(job.w.OUT/'rigid_0.25.json');completed=api.read(job.s.RUN/'completion'/'record.json')
    whole=[job.common_trace(archived['rows']+completed['rows'],rec,source) for rec in records]
    api.require(whole==result['comparison']['whole_trace_errors'],'recomputed complete-trace differences')
    limits=d['acceptance']['limits'];settings=d['acceptance']
    api.require(all(errors[1][k]<=limit and (errors[1][k]<=settings['error_reduction_ratio_max']*errors[0][k] or max(errors[0][k],errors[1][k])<settings['noise_floor']) for k,limit in limits.items()),'three-level accuracy')
    api.require(all(all(row[k]<=limit for k,limit in limits.items()) for row in whole),'full trace accuracy')
    first=api.read(job.RUN/'restart_first.json');second=api.read(job.RUN/'restart_second.json')
    binding=api.digest([d['binding'],'paired_rotational_modes',1.]);initial=job.model.checkpoint(records[0]['spec'],binding,source,True)
    for rec,cp in [(first,initial),(second,first['result']['checkpoint'])]:
        api.require(job.s.check_record(rec,cp,records[0]['spec'],job.model.binding_for(binding,True))['passed'],'restart health and links')
    api.require(first['rows']+second['rows']==records[0]['rows'],'exact restart trace')
    api.require(second['result']['checkpoint']['state']==records[0]['result']['checkpoint']['state'],'exact restart state')
    coarse=api.read(job.w.OUT/'rigid_1.0.json');ratio=len(coarse['rows'])/len(records[0]['rows'])
    api.require(ratio>=2 and ratio==result['step_reduction_factor'],'cost criterion')
    audit={'passed':True,'stages152_and153_seals_and_artifacts_verified':True,'all_independent_checks':checks,
           'three_level_errors':errors,'whole_trace_errors':whole,'exact_restart_state_and_trace':True,
           'step_reduction_factor':ratio,'runtime_ratio_old_over_new':result['runtime_ratio_old_over_new'],
           'claim':d['claim'],'production_promotion':False,'next':'Use the locally qualified modal controller in a separately frozen longer contact-rich test; compare the rotational-inertia and quasistatic assumptions before any release-population campaign.',
           'design_sha256':api.sha(job.DESIGN),'evaluation_sha256':api.sha(job.OUT/'results.json'),
           'source_sha256':api.sha(__file__)}
    OUT.mkdir(parents=True,exist_ok=False);api.write(OUT/'results.json',audit,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
    print('INDEPENDENT_AUDIT_PASS',True,'STEP_REDUCTION',ratio,flush=True)


if __name__=='__main__':main()
