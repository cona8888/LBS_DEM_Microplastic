"""Zero-transport qualification of prospective accounting and actual bindings."""
from pathlib import Path
import copy,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_case_v5 as c


def run():
    c.s.environment();request=c.read(c.REQUEST)
    destination=Path(request['administration_qualification']).parent
    c.require(not destination.exists() and not c.PLAN.exists() and not c.OUT.exists(),
              'Create-only qualification before any configured dispatch')
    checks={}
    def reject(name,fn):
        try:fn()
        except (RuntimeError,ValueError,AssertionError,KeyError):checks[name]=True
        else:raise AssertionError('Negative control admitted: '+name)
    core='hand_case'
    def entry(name,physical,diagnostics,calls):
        return dict(root=name,logical_core_id=core,physical_steps=physical,diagnostic_steps=diagnostics,
                    production_calls=calls,known_unaccepted_steps=0,unknown_steps=0,
                    complete_passed=True,proven_zero_step_implementation_failure=False)
    items=[entry('coarse',100,512,2),entry('fine',200,512,4),entry('third',400,512,8)]
    totals=c.logical_totals(core,items)
    checks['hand_sum_all_three_refinements']=totals==dict(physical_steps=700,diagnostic_steps=1536,production_calls=14)
    reject('duplicate_attempt_rejected',lambda:c.logical_totals(core,items+[items[0]]))
    unrelated=copy.deepcopy(items);unrelated[0]['logical_core_id']='other_case'
    reject('unrelated_predecessor_rejected',lambda:c.logical_totals(core,unrelated))
    unresolved=copy.deepcopy(items);unresolved[0]['unknown_steps']=1
    reject('unknown_work_rejected',lambda:c.logical_totals(core,unresolved))
    failure=copy.deepcopy(items);failure[0]['complete_passed']=False
    reject('incomplete_physical_path_rejected',lambda:c.logical_totals(core,failure))
    wrong_type=copy.deepcopy(items);wrong_type[0]['physical_steps']=True
    reject('boolean_counter_rejected',lambda:c.logical_totals(core,wrong_type))
    edge=dict(maximum_production_steps=5000000-700-1536-512,maximum_production_calls=1500-14)
    c.check_case_budget(totals,edge);checks['exact_original_budget_boundary']=True
    reject('one_extra_step_rejected',lambda:c.check_case_budget(totals,{**edge,'maximum_production_steps':edge['maximum_production_steps']+1}))
    reject('one_extra_call_rejected',lambda:c.check_case_budget(totals,{**edge,'maximum_production_calls':edge['maximum_production_calls']+1}))
    # Exercise the real preserved unlaunched/failed attempts and two complete
    # refinements, without integrating or decoding a new numerical trajectory.
    sphere='p1_i0_equal_volume_sphere_u0p5'
    roots=[str(c.ROOT/'paper1_runs'/name) for name in ('first_core_20261013','first_core_20261013_repair02',
              'first_fine_20261013','first_fine_20261013_repair02')]
    reject('omitted_real_attempt_rejected',lambda:c.logical_ledger(sphere,roots[:-1]))
    real_entries,real_totals,pins=c.logical_ledger(sphere,roots)
    checks['real_preserved_failure_and_refinement_accounting']=(len(real_entries)==4 and
        real_totals==dict(physical_steps=1243392,diagnostic_steps=1024,production_calls=249))
    current_entries,current_totals,_=c.logical_ledger(request['core_id'],request['logical_case_prior_roots'])
    c.check_case_budget(current_totals,request)
    checks['request_ledger_has_only_its_declared_attempts']=len(current_entries)==len(request['logical_case_prior_roots'])
    checks['new_physical_case_inherits_zero_unrelated_steps']=(request['factor']<.125 or (not current_entries and
        current_totals==dict(physical_steps=0,diagnostic_steps=0,production_calls=0)))
    checks['original_transaction_and_context_code_objects']=(c.transaction.__code__ is c.original.transaction.__code__
        and c.make_context.__code__ is c.original.make_context.__code__
        and c.verify_inputs.__code__ is c.original.verify_inputs.__code__
        and c.supervise.__code__ is c.original.supervise.__code__)
    checks['actual_configured_helper_namespace']=all(c.run.__globals__[name] is getattr(c,name)
        for name in ('bound','verify_inputs','make_context','transaction'))
    checks['only_three_original_administrative_ast_changes']=(sum(c.IDENTITY['resource_expressions_changed'].values())==3
        and c.IDENTITY['physical_edits']==c.IDENTITY['accuracy_edits']==0)
    ctx=c.make_context()  # The builder asserts actual original producer/auditor associations.
    checks['original_producer_auditor_associations']=ctx.raw.__code__ is c.s.context.qualified.raw.__code__
    checks['no_dispatch_or_transaction_created']=not c.PLAN.exists() and not c.OUT.exists()
    c.require(all(checks.values()),'All prospective administration controls')
    sources={str(p.resolve()):c.sha(p) for p in (Path(__file__),c.SELF,Path(c.original.__file__))}
    c.seal(destination,dict(passed=True,new_transport_steps=0,request_sha256=c.sha(c.REQUEST),checks=checks,
        real_logical_case_totals=real_totals,current_logical_case_totals=current_totals,
        preserved_attempt_evidence=pins,source_files=sources,utc=c.s.utc()))
    print('PAPER1_ADMINISTRATION_QUALIFIED',c.sha(destination/'results.json'),len(checks),flush=True)


if __name__=='__main__':run()
