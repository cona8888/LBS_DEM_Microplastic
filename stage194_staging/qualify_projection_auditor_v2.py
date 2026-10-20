"""Rerun unchanged zero-step route fixtures after helper collision repair."""
from pathlib import Path
import types
import qualify_projection_auditor_v1 as old
import audit_projection_routes_v2 as auditor
namespace={**old.run.__globals__,'auditor':auditor,'__file__':__file__,'OUT':old.BASE/'route_audit_qualification_02'}
run=types.FunctionType(old.run.__code__,namespace,'run',old.run.__defaults__,old.run.__closure__)

if __name__=='__main__':
    failed=old.OUT/'failure.json'
    if not failed.exists():old.job.commit(failed,{'new_trajectory_steps':0,'error':"TypeError: 'list' object is not callable",'cause':'accepted_route helper was shadowed by the preserved original local list; first fixed-pose audit only; no trajectory launched.','original_source_unchanged':True})
    paths=[Path(__file__),Path(old.__file__),Path(auditor.__file__),Path(auditor.prior.__file__)]
    inputs={str(p):old.api.sha(p) for p in paths};manifest=old.q.ROOT/'stage194_designs/evidence_repair_20260924/route_audit_sources_02.json'
    old.job.commit(manifest,{'source_sha256':inputs,'new_trajectory_steps':0,'same_qualification_bytecode':run.__code__ is old.run.__code__})
    run();old.api.verify_mapping(inputs)
    old.job.commit(namespace['OUT']/'source_closure.json',{'source_manifest_sha256':old.api.sha(manifest),'results_sha256':old.api.sha(namespace['OUT']/'results.json'),'sources_unchanged':True})
