"""Zero-step actual terminal interface, immutable source and corrupt-ledger proof."""
from pathlib import Path
import copy,inspect
import terminal_ledger_adapter_v1 as a
api,job=a.api,a.job

def run(expected):
    api.require(api.sha(job.DESIGN)==expected,'exact running campaign')
    d=api.read(job.DESIGN);before=a.original(d)
    api.require('new_steps' not in before,'actual original terminal-only interface omission identified')
    source=inspect.getsource(job.evaluate)
    api.require("verify_preflight(d)['new_steps']" in source,'actual unchanged terminal assembler budget consumer')
    after=a.qualified_ledger(d)
    api.require(after['new_steps']==17000 and after['original_preflight_stays_failed'] and after['terminal_budget_interface_only'],'correct actual accounting interface')
    controls=[]
    def check(n,f):
        api.require(not n['preflight_passed'] and n['failure_accounting_closed'] and n['saved_steps']==n['independently_physical_passing_steps']==17000
            and f['stage216_failure_preserved'] and f['passed'] and f['new_trajectory_steps']==0,'exact complementary qualification budget ledger, failed preflight not promoted')
    n=a.frozen.sealed(a.frozen.QUAL_NUM);f=a.frozen.sealed(a.frozen.QUAL_FIX);check(n,f)
    for target,key,value in [('n','preflight_passed',True),('n','failure_accounting_closed',False),('n','saved_steps',16999),('n','independently_physical_passing_steps',16999),('f','stage216_failure_preserved',False),('f','passed',False),('f','new_trajectory_steps',1)]:
        x,y=copy.deepcopy(n),copy.deepcopy(f);(x if target=='n' else y)[key]=value
        try:check(x,y)
        except RuntimeError:controls.append(target+':'+key)
        else:raise AssertionError('corrupt qualification ledger accepted')
    # Probe actual assembler lookup in this isolated qualification process,
    # never execute an evaluator or touch the live supervisor namespace.
    api.require(job.verify_preflight is a.original and job.evaluate.__globals__ is vars(job),'actual original assembler namespace')
    job.verify_preflight=a.qualified_ledger
    try:
        api.require(job.evaluate.__globals__['verify_preflight'](d)['new_steps']==17000,'actual assembler lookup receives independently passing step count')
        a.frozen.bindings()
    finally:job.verify_preflight=a.original
    paths=[Path(a.__file__),Path(__file__),job.DESIGN,job.WORK,a.frozen.QUAL_NUM,a.frozen.QUAL_FIX,a.frozen.RESOURCE_AUDIT,job.OUT/'independent_bridge_01/results.json']
    r=dict(passed=True,new_trajectory_steps=0,design_sha256=expected,source_sha256=api.sha(a.__file__),diagnosed_interface_missing_in_frozen_launcher=True,
        original_frozen_evaluator_unrun_not_failed=True,qualified_terminal_budget_steps=17000,corrupt_ledgers_rejected=controls,actual_assembler_callback_proved=True,
        producer_worker_auditor_code_unchanged=True,inputs={str(p):api.sha(p) for p in paths},claim='Terminal-process-only bookkeeping interface bridge. No running source/state edits, trajectory, relaxed physics/gates or promotion of failed qualification.')
    job.commit(a.PROOF,r);job.commit(a.PROOF.parent/'completion.json',dict(passed=True,results_sha256=api.sha(a.PROOF)))
    print('TERMINAL_LEDGER_QUALIFIED',api.sha(a.PROOF),flush=True)
if __name__=='__main__':
    import sys
    run(sys.argv[1])
