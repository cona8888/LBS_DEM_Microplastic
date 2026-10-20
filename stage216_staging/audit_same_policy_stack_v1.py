"""Original full independent audit assertions with new explicit comparator seeds."""
from pathlib import Path
import os,psutil
import same_policy_stack_preflight_v1 as wrapper
api,job=wrapper.api,wrapper.job
sys_source=(wrapper.ROOT/'stage214_staging/audit_normal_gap_stack_v1.py').read_text()
# Retain the qualified birth-aware process retirement function bytecode.
import audit_normal_gap_stack_v1 as prior
from types import FunctionType
retired=FunctionType(prior.retired.__code__,{**prior.retired.__globals__,'job':job},'retired',prior.retired.__defaults__,prior.retired.__closure__)
source=(wrapper.ROOT/'stage200_staging/audit_revised_stack_v1.py').read_text()
changes={
 'import qualify_revised_stack_v1 as composed':'import qualify_same_policy_stack_v1 as composed',
 "r['prior_recovery_steps'] == 78488":"r['prior_stage216_steps'] == 0",
 'actual+78488 == 95488':'actual+0 == 17000',
 "'prior_recovery_steps':78488, 'cumulative_recovery_steps':95488":"'prior_stage216_steps':0, 'stage216_new_accepted_steps':17000, 'separate_prior_policy_saved_steps':10600",
 "'stage200_preflight_steps_verified'":"'stage216_preflight_steps_verified'",
 'STAGE200_INDEPENDENT':'STAGE216_INDEPENDENT',
 "api.require(not any(psutil.pid_exists(pid) for pid in owned), 'every owned process retired')":"retired(owned, live)"
}
for before,after in changes.items():
    api.require(source.count(before)==(2 if before=='STAGE200_INDEPENDENT' else 1),'exact independent audit bookkeeping/identity substitution')
    source=source.replace(before,after)
before="        serial = decode(job.PREFLIGHT/'probes/serial.json.xz')"
extra="""        for case in d['cases']:
            if case['shape']=='equal_volume_sphere':
                fresh_record=decode(job.paths(live,case['id'],1)['raw'])
                independent_fresh=pre.wrapper.reference_record(case,'fresh')
                api.require(fresh_record['rows'][:200]==independent_fresh['rows'],'fresh sphere exact independent same-policy reference')
"""
api.require(source.count(before)==1,'one added stricter independent fresh-reference assertion site')
source=source.replace(before,extra+before)
ns=dict(__name__='_stage216_independent_audit',__file__=__file__,retired=retired)
exec(compile(source,__file__+'::unchanged_physical_and_exact_gates','exec'),ns)

if __name__=='__main__':
    with wrapper.refs.reference.forbid_producer():ns['run']()
