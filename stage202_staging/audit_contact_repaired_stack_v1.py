"""Reuse full independent35-archive/27-numerical audit with new ledger only."""
from pathlib import Path
import contact_repaired_stack_preflight_v1 as wrapper
source=(wrapper.ROOT/'stage200_staging/audit_revised_stack_v1.py').read_text()
changes={
    'import qualify_revised_stack_v1 as composed':'import qualify_contact_repaired_stack_v1 as composed',
    "r['prior_recovery_steps'] == 78488":"r['prior_stage202_steps'] == 0",
    'actual+78488 == 95488':'actual+0 == 17000',
    "'prior_recovery_steps':78488, 'cumulative_recovery_steps':95488":"'prior_stage202_steps':0, 'stage202_new_accepted_steps':17000",
    "'stage200_preflight_steps_verified'":"'stage202_preflight_steps_verified'",
    'STAGE200_INDEPENDENT':'STAGE202_INDEPENDENT',
}
for before,after in changes.items():
    assert before in source,before
    source=source.replace(before,after)
ns={'__name__':'_stage202_independent_audit','__file__':__file__}
exec(compile(source,__file__+'::same_independent_gates','exec'),ns)
if __name__=='__main__':ns['run']()
