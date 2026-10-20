"""Close early only on independently reported resource-policy blocker.

No worker is killed. No production/restart or trajectory call is possible here.
The unlaunched full-preflight preparation must itself refuse the blocked gate.
"""
from pathlib import Path
import os,psutil,sys
import audit_composed_readiness_v1 as audit
import composed_stack_preflight_v1 as preflight
api,job=audit.api,audit.job
OUT=audit.OUT.with_name('work_close_01')

def main():
    # Import/AST binding checks only; never execute its run/probe entry points.
    import qualify_composed_stack_v1
    result=audit.OUT/'results.json';r=api.read(result)
    audit.verify(api.read(audit.DESIGN))
    api.require(api.read(result.parent/'completion.json')['results_sha256']==api.sha(result),'independent audit seal')
    api.require(r['evidence_and_accounting_passed'] and r['no_unresolved_reservation'] and r['cumulative_recovery_steps']==78488,'complete current ledger')
    api.require(r['status']=='qualified_local_implementation_resource_blocked' and not r['resource_screen']['runtime_gate_passed'],'reported major conservative-resource blocker')
    other=[]
    for proc in psutil.process_iter(['pid','name','cmdline','create_time']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower() and 'matdem_microplastic' in ' '.join(proc.info['cmdline'] or []).lower():other.append(proc.info)
    api.require(not other,'every owned diagnostic/audit worker has retired')
    api.require(not preflight.job.DESIGN.exists() and not preflight.job.PREFLIGHT.exists() and not preflight.job.RUN.exists(),'no full-preflight or production launch')
    try:preflight.prepare()
    except Exception as e:
        error=str(e);api.require(error=='late-history resource screen must pass before spending full-preflight steps','only the expected fail-closed gate may reject preparation')
    else:raise AssertionError('full-preflight incorrectly accepted blocked resources')
    api.require(not preflight.job.DESIGN.exists() and not preflight.job.PREFLIGHT.exists() and not preflight.job.RUN.exists(),'gate rejection caused no run/design mutation')
    files=[Path(__file__),Path(preflight.__file__),preflight.job.PREFLIGHT_SCRIPT,audit.DESIGN,result,result.parent/'completion.json',audit.WORK]
    report={'status':'closed_early_resource_policy_blocker','utc':job.utc().isoformat(),'new_trajectory_steps':0,'cumulative_recovery_steps':78488,'remaining_recovery_steps':21512,'all_owned_workers_retired_before_closure':True,'other_owned_workers':other,
            'no_restart_or_forced_termination':True,'full_preflight_and_production_not_launched':True,'fail_closed_preflight_guard':error,'resource_screen':r['resource_screen'],
            'next_gate':'User decision on compute/deadline or conservative resource-planning policy before additional campaign work. Preserve original physics, scientific gates and all failed evidence. Prepared full-preflight scripts remain unexecuted and unqualified; a new clock/accounting handoff is needed after this closed window.',
            'heartbeat':'dem-eight-hour-runtime-optimization; delete via app after this closure exits','inputs':{str(x):api.sha(x) for x in files}}
    job.commit(OUT/'results.json',report);job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')});print('BOUNDED_WORK_CLOSED',api.sha(OUT/'results.json'),flush=True)

if __name__=='__main__':main()
