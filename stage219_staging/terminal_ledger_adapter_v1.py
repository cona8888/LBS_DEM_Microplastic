"""Terminal-process-only interface bridge; no running or frozen source mutation."""
from pathlib import Path
import copy
import normal_gap_campaign_v1 as frozen
api,job=frozen.api,frozen.job
SELF=Path(__file__).resolve()
PROOF=job.OUT/'terminal_ledger_qualification_01/results.json'
original=job.verify_preflight

def qualified_ledger(d):
    inherited=original(d)
    n=frozen.sealed(frozen.QUAL_NUM);f=frozen.sealed(frozen.QUAL_FIX)
    api.require(not n['preflight_passed'] and n['failure_accounting_closed']
        and n['saved_steps']==n['independently_physical_passing_steps']==17000
        and f['stage216_failure_preserved'] and f['passed'] and f['new_trajectory_steps']==0,'exact complementary qualification budget ledger, failed preflight not promoted')
    return dict(inherited,new_steps=17000,terminal_budget_interface_only=True,original_preflight_stays_failed=True)

def install(expected):
    api.require(api.sha(job.DESIGN)==expected,'one frozen campaign only')
    r=frozen.sealed(PROOF);api.verify_mapping(r['inputs'])
    api.require(r['passed'] and r['source_sha256']==api.sha(SELF) and r['design_sha256']==expected and r['new_trajectory_steps']==0,'independently qualified terminal-only adapter')
    api.require(job.verify_preflight is original,'not already installed or unknown preflight callback')
    api.require(job.evaluate.__globals__ is vars(job) and job.evaluate.__globals__['verify_preflight'] is original,'actual original assembler uses the exact verified callback')
    job.verify_preflight=qualified_ledger
    api.require(job.evaluate.__globals__['verify_preflight'] is qualified_ledger,'actual terminal budget adapter association')
    # Only this separately launched process owns the ModuleType namespace.
    # Integration, auditor, worker and physical functions remain byte-identical.
    frozen.bindings();return frozen
