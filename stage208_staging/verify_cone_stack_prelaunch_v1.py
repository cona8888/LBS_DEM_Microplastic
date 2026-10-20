"""Zero-trajectory corruption guards and exact bound route before launch."""
from pathlib import Path
import copy,shutil
import cone_feasibility_stack_preflight_v1 as w
api,job=w.api,w.job

def run():
    d=api.read(job.DESIGN);job.verify(d);w.ledger();w.no_competing_trajectory()
    mutations=[('physics',lambda b:b['cases'][0]['spec']['config'].update(friction_coefficient=.31)),('gates',lambda b:b['numerical_gates'].update(whole_position_over_b_max=.1)),('workers',lambda b:b['budget'].update(workers=6)),('seed',lambda b:b.update(stress_seed_raw='unbound')),('deadline',lambda b:b.update(simulation_cutoff_utc='2030-01-01T00:00:00+00:00')),('production',lambda b:b.update(production_authorized=True)),('step_budget',lambda b:b['preflight'].update(maximum_new_steps=18000)),('audit_route',lambda b:b.update(audit_source_sha256='0'*64)),('receipt_adapter',lambda b:b.update(receipt_adapter_sha256='0'*64))]
    rejected=[]
    for name,change in mutations:
        bad=copy.deepcopy(d);change(bad);bad.pop('binding');bad['binding']=api.digest(bad)
        try:job.verify(bad)
        except (ValueError,RuntimeError,AssertionError):rejected.append(name)
        else:raise AssertionError('accepted corrupt design '+name)
    original=job.execute_segment.__globals__['repair']
    try:
        job.execute_segment.__globals__['repair']=w.repair.prior
        try:job.verify(d)
        except (ValueError,RuntimeError,AssertionError):rejected.append('wrong_in_memory_repair_binding')
        else:raise AssertionError('wrong repair binding accepted')
    finally:job.execute_segment.__globals__['repair']=original
    api.require(len(rejected)==10,'all corrupt designs/bindings rejected')
    free=shutil.disk_usage(w.ROOT).free;api.require(free>d['budget']['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'bounded reserve')
    inputs={str(p):api.sha(p) for p in (Path(__file__),job.DESIGN,w.CLOSE,w.LOCAL_QUAL)}
    result=dict(passed=True,new_trajectory_steps=0,mutation_rejections=rejected,free_bytes=free,design_sha256=api.sha(job.DESIGN),inputs=inputs,claim='Software/numerical binding checks only. No production launched.')
    out=job.OUT/'prelaunch_01';job.commit(out/'results.json',result);job.commit(out/'completion.json',dict(passed=True,results_sha256=api.sha(out/'results.json')))
    print('CONE_STACK_PRELAUNCH_PASS',rejected,flush=True)
if __name__=='__main__':run()
