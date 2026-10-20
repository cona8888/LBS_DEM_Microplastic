"""Audit cost-only output independently; do not infer convergence from timing."""
import copy
import numpy as np
import spatial_cost_v1 as job


def assess(r,d,relative,absolute):
    timed=[x for x in r['blocks'] if x['role']=='timed']
    return {'exact_417_steps':r['steps_completed']==417,
        'frozen_blocks':[(x['steps'],x['end_step']) for x in r['blocks']]==[(32,32),(128,160),(128,288),(128,416)],
        'finite_positive_times':all(np.isfinite(x['kernel_s']) and x['kernel_s']>0 and x['wall_s']>=x['kernel_s'] for x in r['blocks']),
        'exact_device_allocation':r['device_allocation_bytes']==d['cost_model']['device_bytes'],
        'numerical_health':r['health_code']==0 and all(x['health_code']==0 for x in r['blocks']),
        'states_finite':r['finite_states'] is True,'solids_zero':r['solid_populations_zero'] is True,
        'within_cooperative_budget':r['wall_total_s']<=d['pilot']['wall_budget_s'],
        'cpu_gpu_transition_relative':np.isfinite(relative) and relative<=d['pilot']['transition_relative_l2_max'],
        'cpu_gpu_transition_absolute':np.isfinite(absolute) and absolute<=d['pilot']['transition_absolute_max'],
        'qualified_binary':r['build']['ptx_sha256']==d['qualified_ptx_sha256'],
        'no_flow_or_transport_claim':all(r[k] is False for k in ['steady_state','mean_matched','flow_field_exported','transport_authorized'])}


def main():
    d=job.read(job.DESIGN);job.verify(d)
    done=job.read(job.RUN/'completion.json');r=job.read(job.RUN/'result.json')
    job.require(not (job.RUN/'failure.json').exists(),'failure exists')
    job.require(done['results_sha256']==job.sha(job.RUN/'result.json'),'result drift')
    for path,expected in done['artifacts'].items():job.require(job.sha(path)==expected,'run artifact drift')
    job.require(r['design_sha256']==job.sha(job.DESIGN) and r['manifest_sha256']==job.sha(job.RUN/'manifest.json'),'source manifest drift')
    with np.load(r['transition_samples']['path']) as data:
        pre,actual,nodes=data['precollision'],data['next_stored'],data['nodes_zyx']
    job.require(pre.shape==actual.shape==(64,19) and len(np.unique(nodes,axis=0))==64,'transition sample structure')
    oracle=job.prior.audit.legacy.stage13.arbitrary.frozen_projected_collision_node
    calculated=np.array([oracle(row,.8,d['pilot']['acceleration_lu']) for row in pre])
    errors=np.linalg.norm(calculated.astype(float)-actual,axis=1)/np.maximum(np.linalg.norm(actual.astype(float),axis=1),1e-30)
    relative=float(errors.max());absolute=float(np.max(np.abs(calculated.astype(float)-actual)))
    checks=assess(r,d,relative,absolute)
    tests=[]
    for key,value in [('steps_completed',416),('health_code',1),('finite_states',False),('steady_state',True),('device_allocation_bytes',0)]:
        broken=copy.deepcopy(r);broken[key]=value
        tests.append(not all(assess(broken,d,relative,absolute).values()))
    tests += [not all(assess(r,d,float('nan'),absolute).values()),not all(assess(r,d,relative,1.).values())]
    checks['seven_error_injection_tests']=all(tests)
    times=[x['kernel_s']/x['steps'] for x in r['blocks'] if x['role']=='timed']
    worst=max(times);margin=d['cost_model']['scenario_time_safety_multiplier']
    scenarios=[{'assumed_steps':n,'kernel_hours_at_median':n*float(np.median(times))/3600,
                'kernel_hours_with_margin':n*worst*margin/3600,
                'within_six_hour_kernel_budget':n*worst*margin<=d['cost_model']['full_solve_budget_s']} for n in d['cost_model']['scenario_steps']]
    result={'passed':all(checks.values()),'checks':{k:bool(v) for k,v in checks.items()},
        'design':job.bind(job.DESIGN),'raw_completion':job.bind(job.RUN/'completion.json'),
        'cpu_transition_max_relative_l2':relative,'cpu_transition_max_absolute':absolute,
        'kernel_seconds_per_step':times,'median_kernel_seconds_per_step':float(np.median(times)),
        'device_GiB':r['device_allocation_bytes']/1024**3,'wall_total_s':r['wall_total_s'],
        'conditional_cost_scenarios':scenarios,
        'maximum_kernel_steps_in_six_hours_with_margin':int(d['cost_model']['full_solve_budget_s']/(worst*margin)),
        'status':'geometry_and_cost_verified_full_spatial_solve_still_gated',
        'full_steady_solve_authorized':False,'spatial_convergence_established':False,'empirical_validation_passed':False,
        'next':'Use the measured step cost to bound a CPD4-initialized CPD6 relaxation; directly control achieved mean and apply both-parity steady gates before any paired trajectories.',
        'limitation':'Cost scenarios exclude host diagnostics, initialization, output and possible forcing corrections. Cold-state timing does not predict the number of steps to convergence.'}
    out=job.EVAL/'independent_evaluation_01';out.mkdir(parents=True,exist_ok=False)
    job.write(out/'results.json',result)
    job.write(out/'completion.json',{'passed':result['passed'],'results_sha256':job.sha(out/'results.json')})
    print(job.json.dumps(result,indent=2),flush=True)
    job.require(result['passed'],'pilot verification failed')


if __name__=='__main__':main()
