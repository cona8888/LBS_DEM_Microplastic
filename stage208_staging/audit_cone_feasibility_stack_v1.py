"""Original full independent raw/numerical gates; new ledger/identity only."""
from pathlib import Path
import os,psutil
import cone_feasibility_stack_preflight_v1 as wrapper
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
        if 'python' not in (p.info['name'] or '').lower():continue
        try:api.require(not scripts.intersection(os.path.normcase(os.path.normpath(x)) for x in p.cmdline()),'no same-command owned process alive')
        except psutil.NoSuchProcess:continue

source=(wrapper.ROOT/'stage200_staging/audit_revised_stack_v1.py').read_text()
changes={
 'import qualify_revised_stack_v1 as composed':'import qualify_cone_feasibility_stack_v1 as composed',
 "r['prior_recovery_steps'] == 78488":"r['prior_stage208_steps'] == 0",
 'actual+78488 == 95488':'actual+0 == 17000',
 "'prior_recovery_steps':78488, 'cumulative_recovery_steps':95488":"'prior_stage208_steps':0, 'stage208_new_accepted_steps':17000",
 "'stage200_preflight_steps_verified'":"'stage208_preflight_steps_verified'",
 'STAGE200_INDEPENDENT':'STAGE208_INDEPENDENT',
 "api.require(not any(psutil.pid_exists(pid) for pid in owned), 'every owned process retired')":"retired(owned, live)"
}
for before,after in changes.items():
    assert source.count(before)==(2 if before=='STAGE200_INDEPENDENT' else 1),before
    source=source.replace(before,after)
ns=dict(__name__='_stage208_independent_audit',__file__=__file__,retired=retired)
exec(compile(source,__file__+'::unchanged_physical_gates','exec'),ns)
if __name__=='__main__':ns['run']()
