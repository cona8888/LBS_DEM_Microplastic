"""Configured Paper1 windows with exact logical-case accounting and audit reserves.

Only window/case administration is generalized. The frozen v2 run code is
cloned with three resource-cap expressions changed to prospective plan values.
No integration, force, archive, physical or accuracy code is reimplemented.
"""
from pathlib import Path
from types import FunctionType
from datetime import datetime,timezone,timedelta
import ast,inspect,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_core_v2 as original
s=original.s;ROOT=s.ROOT;SELF=Path(__file__).resolve();PYTHON=s.PYTHON
REQUEST=Path(os.environ['DEM_PAPER1_REQUEST']).resolve()
DESIGNS=REQUEST.parent;PLAN=DESIGNS/'design_01.json';AUTH=DESIGNS/'authorization_01.json';PHYSICAL=DESIGNS/'physical_cases_01.json'
OUT=ROOT/'paper1_runs'/DESIGNS.name
sha,read,require,commit,seal=original.sha,original.read,original.require,original.commit,original.seal
DOC=original.DOC


def clone(fn,ns):return FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__)
namespace={**vars(original),**globals()}
original_bound=clone(original.bound,namespace)
def bound():
    p=original_bound()
    retained=sum(path.stat().st_size for dirname in ('paper1_runs','paper1_designs','paper1_evaluations')
                 for path in (ROOT/dirname).rglob('*') if path.is_file())
    require(retained<20*1024**3,'Total declared Paper1 retained-data ceiling')
    return p
verify_inputs=clone(original.verify_inputs,namespace)
make_context=clone(original.make_context,namespace);transaction=clone(original.transaction,namespace)


def logical_totals(core_id,entries):
    seen=set();physical=diagnostics=calls=0
    for item in entries:
        require(item['logical_core_id']==core_id and item['root'] not in seen,
                'All and only unique attempts of the same logical case')
        seen.add(item['root'])
        for key in ('physical_steps','diagnostic_steps','production_calls','known_unaccepted_steps','unknown_steps'):
            require(type(item[key]) is int and item[key]>=0,'Exact nonnegative ledger counter')
        require(item['known_unaccepted_steps']==item['unknown_steps']==0,'No unresolved prior work')
        require(item['complete_passed'] or (item['proven_zero_step_implementation_failure']
            and item['physical_steps']==item['diagnostic_steps']==item['production_calls']==0),
            'No dependent dispatch after a failed or incomplete physical path')
        physical+=item['physical_steps'];diagnostics+=item['diagnostic_steps'];calls+=item['production_calls']
    return dict(physical_steps=physical,diagnostic_steps=diagnostics,production_calls=calls)


def check_case_budget(totals,request):
    require(type(request['maximum_production_steps']) is int and request['maximum_production_steps']>0
        and type(request['maximum_production_calls']) is int and request['maximum_production_calls']>0,
        'Positive integer prospective caps')
    require(totals['physical_steps']+totals['diagnostic_steps']+request['maximum_production_steps']+512<=5000000
        and totals['production_calls']+request['maximum_production_calls']<=1500,
        'Original grouped limits include every same-case refinement and all diagnostics conservatively')


def logical_ledger(core_id,declared_roots):
    plans=[p for p in sorted((ROOT/'paper1_designs').glob('*/design_01.json'))
           if read(p).get('logical_core_id')==core_id]
    expected={str((ROOT/'paper1_runs'/p.parent.name).resolve()) for p in plans}
    declared=[str(Path(p).resolve()) for p in declared_roots]
    require(len(declared)==len(set(declared)) and set(declared)==expected,
            'Explicit inventory includes every prior same-case attempt, never an unrelated predecessor')
    entries=[];pins={}
    for plan_path in plans:
        root=ROOT/'paper1_runs'/plan_path.parent.name;past=read(plan_path)
        pins[str(plan_path)]=sha(plan_path)
        def pin(folder):
            for name in ('results.json','completion.json'):
                path=folder/name;pins[str(path)]=sha(path)
        if not (root/'final_disposition_01/results.json').exists():
            proof=s.fields.sealed(root/'unlaunched_diagnosis_01/results.json')
            require(proof['design_sha256']==sha(plan_path) and proof['zero_dispatch'] and proof['preserved']
                and proof['new_saved_steps']==0 and not (root/'records').exists()
                and not list(root.rglob('*launch*.json')),'Authenticated zero-dispatch implementation failure')
            pin(root/'unlaunched_diagnosis_01')
            entries.append(dict(root=str(root),logical_core_id=core_id,physical_steps=0,diagnostic_steps=0,
                production_calls=0,known_unaccepted_steps=0,unknown_steps=0,complete_passed=False,
                proven_zero_step_implementation_failure=True));continue
        final=s.fields.sealed(root/'final_disposition_01/results.json')
        retired=s.fields.sealed(root/'retirement_01/results.json')
        require(final['design_sha256']==retired['design_sha256']==sha(plan_path)
            and retired['final_disposition_sha256']==sha(root/'final_disposition_01/results.json')
            and retired['all_exact_owned_identities_retired'],'Ledger binds the exact retired attempt')
        for item in retired['identities']:
            require(sha(item['path'])==item['sha256'] and s.identity(read(item['path']))['retired'],
                    'Fresh birth AND command retirement for every prior identity')
        for key in ('artifacts','closed_logs','source_files','inputs'):
            if key in retired:s.api.verify_mapping(retired[key])
        s.api.verify_mapping(past['source_files']);s.api.verify_mapping(past['physical_inputs'])
        complete=bool(final['passed'] and final['native_complete'] and retired['passed'])
        zero=bool(retired.get('accounting_authenticated') and retired.get('coarse_all_artifacts_reauthenticated_unchanged')
            and retired.get('new_saved_steps')==0 and retired.get('no_actual_transaction_directory'))
        entries.append(dict(root=str(root),logical_core_id=core_id,physical_steps=final['accepted_physical_steps'],
            diagnostic_steps=final['discarded_diagnostic_steps'],production_calls=len(final['production_labels']),
            known_unaccepted_steps=final['known_unaccepted_saved_steps'],unknown_steps=final['unknown_reserved_steps_upper_bound'],
            complete_passed=complete,proven_zero_step_implementation_failure=zero))
        pin(root/'final_disposition_01');pin(root/'retirement_01')
    return entries,logical_totals(core_id,entries),pins


def approved_storage():
    path=ROOT/'paper1_designs/p1_i0_fibre_u0p5_accuracy_recovery_20261014/human_budget_approval_01/results.json'
    approval=s.fields.sealed(path)
    require(sha(path)=='301e4afe28da34268d5ab287d948e44f7819f894987d6b3fbcf29113aba56270'
        and approval['human_response']=='Approve this bounded finer reference (Recommended)'
        and approval['total_retained_gib']==20 and approval['no_automatic_budget_expansion'] is True,
        'Explicit approved total Paper1 storage limit; other logical cases keep original5M/1500 ceilings')
    return {str(path):sha(path),str(path.with_name('completion.json')):sha(path.with_name('completion.json'))}


def prepare():
    s.environment();require(not PLAN.exists() and not OUT.exists(),'Fresh configured window')
    request=read(REQUEST)
    require(0<request['hours']<=12 and request['factor'] in (.125,.0625,.03125),'Declared window/refinement domain')
    qualification_path=Path(request['administration_qualification'])
    qualification=s.fields.sealed(qualification_path)
    require(qualification['passed'] and qualification['new_transport_steps']==0
        and qualification['request_sha256']==sha(REQUEST)
        and qualification['source_files'][str(SELF)]==sha(SELF),'Qualified exact administration and request')
    s.api.verify_mapping(qualification['source_files'])
    prerequisite=Path(request['prerequisite_root']);retired=s.fields.sealed(prerequisite/'retirement_01/results.json')
    final=s.fields.sealed(prerequisite/'final_disposition_01/results.json')
    require(retired['passed'] and retired['all_exact_owned_identities_retired'] and final['passed'] and final['native_complete']
        and final['known_unaccepted_saved_steps']==final['unknown_reserved_steps_upper_bound']==0,'Complete retired predecessor before dispatch')
    previous_plan_path=ROOT/'paper1_designs'/prerequisite.name/'design_01.json'
    previous_plan=read(previous_plan_path)
    require(retired['design_sha256']==final['design_sha256']==sha(previous_plan_path)
        and retired['final_disposition_sha256']==sha(prerequisite/'final_disposition_01/results.json'),
        'Predecessor final/retirement bind its exact plan')
    if request['factor']<.125:
        previous_case=read(ROOT/'paper1_designs'/prerequisite.name/'physical_cases_01.json')['cases'][0]
        require(request['core_id']==previous_plan['logical_core_id'] and previous_case['factor']==2*request['factor'],
                'Numerical reference follows the same physical case at the adjacent original refinement')
    if request['factor'] in (.125,.03125):
        comparison_path=Path(request['prerequisite_comparison'])
        comparison=s.fields.sealed(comparison_path)
        require(comparison['passed'] and comparison['whole_start_to_terminal_paths']
            and comparison['full_path_gates']['passed'] and comparison['logical_core_id']==previous_plan['logical_core_id']
            and comparison['evidence_files'][str((prerequisite/'final_disposition_01/results.json').resolve())]
                ==sha(prerequisite/'final_disposition_01/results.json'),
            'Next physical/third-level case requires the exact predecessor whole-path accuracy')
        for key in ('path_artifacts','evidence_files','source_files'):s.api.verify_mapping(comparison[key])
    entries,totals,ledger_pins=logical_ledger(request['core_id'],request['logical_case_prior_roots'])
    check_case_budget(totals,request)
    for item in retired['identities']:
        launch=read(item['path']);require(s.identity(launch)['retired'],'Fresh exact predecessor retirement')
    case,field,data=s.factory.load_case(request['core_id'],.01,request['factor'],'core');del field,data
    template=s.factory.contract();source=read(template['physical_design_file'])
    physical=dict(schema='paper1.configured-physical.v1',cases=[case],minimum_gap_semantics=source['minimum_gap_semantics'],
        original_template_sha256=template['physical_design_sha256'],exposure_decision_sha256=sha(s.factory.EXPOSURE),
        physical_equation_changes=[],accuracy_gate_changes=[])
    physical['binding']=s.api.digest(physical)
    inherited=read(ROOT/'paper1_designs/first_core_20261013_repair02/design_01.json')
    inputs={**inherited['physical_inputs'],**ledger_pins,str(REQUEST):sha(REQUEST),
        str(qualification_path):sha(qualification_path),
        str(qualification_path.with_name('completion.json')):sha(qualification_path.with_name('completion.json'))}
    inputs.update(qualification['preserved_attempt_evidence']);inputs.update(approved_storage())
    if 'repair_predecessor_root' in request:
        failed=Path(request['repair_predecessor_root'])
        negative=s.fields.sealed(failed/'retirement_01/results.json')
        require(negative['accounting_authenticated'] and negative['all_exact_owned_identities_retired']
            and negative['new_saved_steps']==negative['known_unaccepted_saved_steps']==negative['unknown_reserved_steps_upper_bound']==0
            and negative['coarse_all_artifacts_reauthenticated_unchanged'],'Exact retired zero-step implementation failure')
        failed_plan=read(ROOT/'paper1_designs'/failed.name/'design_01.json')
        require(request['absolute_end_utc']==failed_plan['end_utc']
            and request['maximum_production_steps']==failed_plan['maximum_production_steps']
            and request['maximum_production_calls']==failed_plan['maximum_production_calls'],
            'No repair deadline or shared-cap extension')
        for item in negative['identities']:require(s.identity(read(item['path']))['retired'],'Failed exact identities remain retired')
        for path in (failed/'retirement_01/results.json',failed/'retirement_01/completion.json',
                     failed/'final_disposition_01/results.json',ROOT/'paper1_designs'/failed.name/'design_01.json'):
            inputs[str(path)]=sha(path)
    if request['factor'] in (.125,.03125):
        inputs[str(comparison_path)]=sha(comparison_path)
        inputs[str(comparison_path.with_name('completion.json'))]=sha(comparison_path.with_name('completion.json'))
    for path in (prerequisite/'retirement_01/results.json',prerequisite/'retirement_01/completion.json',
                 prerequisite/'final_disposition_01/results.json',prerequisite/'final_disposition_01/completion.json'):
        inputs[str(path)]=sha(path)
    inputs.update(s.context.fields.dependencies(case['spec']['field_metadata']))
    imported={str(Path(m.__file__).resolve()):sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py'
        and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources={**inherited['source_files'],**imported,**qualification['source_files']};s.api.verify_mapping(inputs);s.api.verify_mapping(sources)
    start=datetime.now(timezone.utc);end=datetime.fromisoformat(request['absolute_end_utc']) if 'absolute_end_utc' in request else start+timedelta(hours=request['hours'])
    simulation_reserve=request.get('simulation_reserve_minutes',75);worker_reserve=request.get('worker_reserve_minutes',35)
    require(12<=worker_reserve<simulation_reserve and simulation_reserve>=25
        and simulation_reserve*60+90<(end-start).total_seconds()<=request['hours']*3600,
        'Bounded window with conservative raw reconstruction/retirement/comparison reserves')
    auth=dict(human_authorization='Complete agreed Paper1 set and original full-path numerical qualification, fresh configured bounded window.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=simulation_reserve)).isoformat(),
        worker_cutoff_utc=(end-timedelta(minutes=worker_reserve)).isoformat(),step_cap_per_call=5000,
        maximum_saved_steps=request['maximum_production_steps']+512,maximum_production_steps=request['maximum_production_steps'],
        maximum_production_calls=request['maximum_production_calls'],maximum_cumulative_physical_steps_per_case=5000000,
        maximum_cumulative_calls_per_case=1500,workers=1,threads=1,maximum_unverified_records=1,logical_cpu=14,
        minimum_free_disk_bytes=20*1024**3,maximum_output_bytes=4*1024**3,no_timestep_escalation=True,retain_all_failures=True,
        accuracy_promotion_authorized=False,successor_cases_authorized=False)
    require(auth['maximum_production_steps']<=5000000 and auth['maximum_production_calls']<=1500,'Original per-case ceilings')
    commit(AUTH,auth);commit(PHYSICAL,physical);inputs[str(PHYSICAL)]=sha(PHYSICAL)
    p={**auth,'authorization_sha256':sha(AUTH),'physical_design_sha256':sha(PHYSICAL),'source_files':sources,
        'physical_inputs':inputs,'case_id':case['id'],'logical_core_id':request['core_id'],
        'numerical_policy_contract_sha256':sha(s.q.job.WORK),'administrative_ast_identity':IDENTITY,
        'prerequisite_root':str(prerequisite),'storage_protocol':inherited['storage_protocol']}
    p['logical_case_preceding_physical_steps']=totals['physical_steps']
    p['logical_case_preceding_diagnostic_steps']=totals['diagnostic_steps']
    p['logical_case_preceding_production_calls']=totals['production_calls']
    p['logical_case_attempt_ledger']=entries
    p['binding']=s.api.digest(p);commit(PLAN,p)
    seal(OUT/'preparation_01',dict(passed=True,design_sha256=sha(PLAN),new_steps=0,utc=s.utc()))
    print('PAPER1_WINDOW_PREPARED',sha(PLAN),p['end_utc'],flush=True)


def build_run():
    tree=ast.parse(inspect.getsource(original.run));counts={}
    replacements={
        'range(1, 126)':"range(1,p['maximum_production_calls']+1)",
        'accepted >= 500000':"accepted>=p['maximum_production_steps']",
        'min(5000, 500000 - accepted)':"min(5000,p['maximum_production_steps']-accepted)"}
    class Change(ast.NodeTransformer):
        def visit(self,node):
            text=ast.unparse(node)
            if text in replacements:
                counts[text]=counts.get(text,0)+1
                return ast.copy_location(ast.parse(replacements[text],mode='eval').body,node)
            return super().visit(node)
    Change().visit(tree)
    require(counts=={key:1 for key in replacements},'Exactly three administrative resource expressions')
    ast.fix_missing_locations(tree);local={**namespace,**globals()};exec(compile(tree,str(SELF)+'::window_caps_only','exec'),local)
    for name in ('bound','verify_inputs','make_context','transaction'):
        require(local[name] is globals()[name],'Actual configured run helper binding: '+name)
    for name in ('PLAN','AUTH','OUT','PHYSICAL'):
        require(local[name]==globals()[name],'Actual configured output/design: '+name)
    return local['run'],dict(resource_expressions_changed=counts,physical_edits=0,accuracy_edits=0)


run,IDENTITY=build_run()
namespace.update(globals())
supervise=clone(original.supervise,{**original.supervise.__globals__,**namespace})
if __name__=='__main__':{'prepare':prepare,'run':run,'supervise':supervise}[sys.argv[1]]()
