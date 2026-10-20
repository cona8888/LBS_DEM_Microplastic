"""Original zero-step bridge controls plus explicit exact-reference provenance."""
from pathlib import Path
from types import FunctionType
import same_policy_stack_preflight_v1 as w
import qualify_same_policy_stack_v1 as pre
import audit_normal_gap_bridge_v1 as original
api,job=w.api,w.job
OUT=job.OUT/'independent_bridge_01'
# The original checks compare original assertion ASTs and corrupt twelve design
# fields/two actual associations, not old output values or altered tolerances.
run=FunctionType(original.run.__code__,{**original.run.__globals__,'w':w,'pre':pre,'job':job,'api':api,'OUT':OUT,'__file__':__file__},'run',original.run.__defaults__,original.run.__closure__)

if __name__=='__main__':
    run()
    d=api.read(job.DESIGN);close=w.sealed(w.REFERENCE);checks=[]
    for case in d['cases']:
        before,oracle=pre.seed(d,case)
        if case['shape']=='equal_volume_sphere':
            expected=w.reference_record(case,'contact');fresh=w.reference_record(case,'fresh')
            api.require(oracle==expected and len(oracle['rows'])==1000 and len(fresh['rows'])==200,'explicit complete same-policy sphere reference')
            old_fresh=w.q.independent_file(w.ROOT/'stage195_runs/repaired_stack_preflight_20260925/preflight_01/probes'/(case['id']+'_fresh.json.xz'),api.sha(pre.tests.prior.job.DESIGN))
            api.require(fresh['rows']==old_fresh['rows'],'original fresh sphere exact reference remains unchanged')
            checks.append(dict(case=case['id'],reference_raw_sha256=api.sha(w.refs.RUN/(case['id']+'_contact')/'call.json.xz'),
                independent_source_sha256=api.sha(w.refs.reference.__file__),full_old_seed_state_unchanged=True,original_fresh_reference_exact=True))
    proof=dict(passed=True,new_trajectory_steps=0,exact_reference_contract_sha256=api.sha(w.refs.WORK),reference_qualification_sha256=api.sha(w.REFERENCE),
        sphere_comparators=checks,old_stage214_remains_failed=True,physical_gate_changes=0,design_sha256=api.sha(job.DESIGN))
    job.commit(OUT/'explicit_reference_selection.json',proof)
    print('EXPLICIT_SAME_POLICY_REFERENCE_BRIDGE',len(checks),api.sha(OUT/'explicit_reference_selection.json'),flush=True)
