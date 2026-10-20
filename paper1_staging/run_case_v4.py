"""Configured Paper1 windows with actual helper-namespace binding checks.

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
REQUEST=Path(os.environ.get('DEM_PAPER1_REQUEST',str(ROOT/'paper1_designs/first_fine_20261013_repair02/request_01.json'))).resolve()
DESIGNS=REQUEST.parent;PLAN=DESIGNS/'design_01.json';AUTH=DESIGNS/'authorization_01.json';PHYSICAL=DESIGNS/'physical_cases_01.json'
OUT=ROOT/'paper1_runs'/DESIGNS.name
sha,read,require,commit,seal=original.sha,original.read,original.require,original.commit,original.seal
DOC=original.DOC


def clone(fn,ns):return FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__)
namespace={**vars(original),**globals()}
original_bound=clone(original.bound,namespace)
def bound():
    p=original_bound()
    retained=sum(path.stat().st_size for dirname in ('paper1_runs','paper1_designs')
                 for path in (ROOT/dirname).rglob('*') if path.is_file())
    require(retained<18*1024**3,'Total declared Paper1 retained-data ceiling')
    return p
verify_inputs=clone(original.verify_inputs,namespace)
make_context=clone(original.make_context,namespace);transaction=clone(original.transaction,namespace)


def prepare():
    s.environment();require(not PLAN.exists() and not OUT.exists(),'Fresh configured window')
    request=read(REQUEST)
    require(request['hours']<=12 and request['factor'] in (.125,.0625,.03125),'Declared window/refinement domain')
    prerequisite=Path(request['prerequisite_root']);retired=s.fields.sealed(prerequisite/'retirement_01/results.json')
    final=s.fields.sealed(prerequisite/'final_disposition_01/results.json')
    require(retired['passed'] and retired['all_exact_owned_identities_retired'] and final['passed'] and final['native_complete']
        and final['known_unaccepted_saved_steps']==final['unknown_reserved_steps_upper_bound']==0,'Complete retired predecessor before dispatch')
    previous_plan=read(ROOT/'paper1_designs'/prerequisite.name/'design_01.json')
    if request['factor']<.125:
        require(request['core_id']==previous_plan['logical_core_id'],
                'Numerical reference may follow only the same physical case')
    else:
        comparison_path=Path(request['prerequisite_comparison'])
        comparison=s.fields.sealed(comparison_path)
        require(comparison['passed'] and comparison['whole_start_to_terminal_paths']
            and comparison['full_path_gates']['passed'],'Next physical case requires predecessor whole-path accuracy')
        s.api.verify_mapping(comparison['path_artifacts'])
    require(final['accepted_physical_steps']+request['maximum_production_steps']+512<=5000000
        and len(final['production_labels'])+request['maximum_production_calls']<=1500,
        'Original logical-case aggregate includes the coarse prerequisite')
    for item in retired['identities']:
        launch=read(item['path']);require(s.identity(launch)['retired'],'Fresh exact predecessor retirement')
    case,field,data=s.factory.load_case(request['core_id'],.01,request['factor'],'core');del field,data
    template=s.factory.contract();source=read(template['physical_design_file'])
    physical=dict(schema='paper1.configured-physical.v1',cases=[case],minimum_gap_semantics=source['minimum_gap_semantics'],
        original_template_sha256=template['physical_design_sha256'],exposure_decision_sha256=sha(s.factory.EXPOSURE),
        physical_equation_changes=[],accuracy_gate_changes=[])
    physical['binding']=s.api.digest(physical)
    inherited=read(ROOT/'paper1_designs/first_core_20261013_repair02/design_01.json')
    inputs={**inherited['physical_inputs'],str(REQUEST):sha(REQUEST)}
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
    if request['factor']==.125:
        inputs[str(comparison_path)]=sha(comparison_path)
        inputs[str(comparison_path.with_name('completion.json'))]=sha(comparison_path.with_name('completion.json'))
    for path in (prerequisite/'retirement_01/results.json',prerequisite/'retirement_01/completion.json',
                 prerequisite/'final_disposition_01/results.json',prerequisite/'final_disposition_01/completion.json'):
        inputs[str(path)]=sha(path)
    inputs.update(s.context.fields.dependencies(case['spec']['field_metadata']))
    imported={str(Path(m.__file__).resolve()):sha(m.__file__) for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py'
        and ROOT in Path(m.__file__).resolve().parents and Path(m.__file__).is_file()}
    sources={**inherited['source_files'],**imported};s.api.verify_mapping(inputs);s.api.verify_mapping(sources)
    start=datetime.now(timezone.utc);end=datetime.fromisoformat(request['absolute_end_utc']) if 'absolute_end_utc' in request else start+timedelta(hours=request['hours'])
    auth=dict(human_authorization='Complete agreed Paper1 set and original full-path numerical qualification, fresh configured bounded window.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=25)).isoformat(),
        worker_cutoff_utc=(end-timedelta(minutes=12)).isoformat(),step_cap_per_call=5000,
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
    p['logical_case_preceding_physical_steps']=final['accepted_physical_steps']
    p['logical_case_preceding_production_calls']=len(final['production_labels'])
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
