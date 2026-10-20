"""Original independent 35-archive/27-record assertions; new contract identity."""
from pathlib import Path
import os,psutil
import normal_gap_stack_preflight_v1 as wrapper
api,job=wrapper.api,wrapper.job

def retired(owned,live):
    terminal=api.read(live/'completion.json');ended=job.policy.utc(terminal['utc']).timestamp()
    scripts={os.path.normcase(str(p.resolve())) for p in (job.SELF,job.PREFLIGHT_SCRIPT)}
    for pid in owned:
        try:
            p=psutil.Process(pid);cmd=p.cmdline()
            api.require(p.create_time()>ended and not scripts.intersection(os.path.normcase(os.path.normpath(x)) for x in cmd),'no live original owned process identity')
        except psutil.NoSuchProcess:continue
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:api.require(not scripts.intersection(os.path.normcase(os.path.normpath(x)) for x in p.cmdline()),'no same-command owned process alive')
        except psutil.NoSuchProcess:continue

source=(wrapper.ROOT/'stage200_staging/audit_revised_stack_v1.py').read_text()
changes={
 'import qualify_revised_stack_v1 as composed':'import qualify_normal_gap_stack_v1 as composed',
 "r['prior_recovery_steps'] == 78488":"r['prior_stage214_steps'] == 0",
 'actual+78488 == 95488':'actual+0 == 17000',
 "'prior_recovery_steps':78488, 'cumulative_recovery_steps':95488":"'prior_stage214_steps':0, 'stage214_new_accepted_steps':17000, 'separate_stage213_saved_and_independently_accepted_steps':4000",
 "'stage200_preflight_steps_verified'":"'stage214_preflight_steps_verified'",
 'STAGE200_INDEPENDENT':'STAGE214_INDEPENDENT',
 "api.require(not any(psutil.pid_exists(pid) for pid in owned), 'every owned process retired')":"retired(owned, live)"
}
for before,after in changes.items():
    api.require(source.count(before)==(2 if before=='STAGE200_INDEPENDENT' else 1),'exact independent audit substitution '+before)
    source=source.replace(before,after)
ns=dict(__name__='_stage214_independent_audit',__file__=__file__,retired=retired)
exec(compile(source,__file__+'::unchanged_physical_and_exact_gates','exec'),ns)

if __name__=='__main__':
    # Independence is executable: this process must never invoke the producer
    # gap classifier. The unchanged kernel uses its rational gap reconstruction.
    original=wrapper.local.policy_scope.policy.classify
    def forbidden(*args,**kwargs):raise AssertionError('producer classifier invoked by independent stack audit')
    wrapper.local.policy_scope.policy.classify=forbidden
    try:ns['run']()
    finally:wrapper.local.policy_scope.policy.classify=original
