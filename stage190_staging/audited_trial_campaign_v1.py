"""New immutable campaign instance; unchanged Stage187 lifecycle and physics.

Only raw observation is extended with Stage189 provenance; the new auditor
uses exact inner-trial rather than intermediate-to-final velocity association.
Fresh production still requires the full new preflight and resource gate.
"""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import inspect
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage189_staging'), str(ROOT/'stage187_staging')]
import contact_trial_trace_v1 as observer
import audit_optimized_record_v4 as new_kernel
import qualify_trial_trace_v3 as qualification
import integrated_paired_campaign_v1 as historical
import qualify_integrated_campaign_v1 as historical_preflight

spec = importlib.util.spec_from_file_location('_stage190_frozen_lifecycle', historical.__file__)
job = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = job
spec.loader.exec_module(job)
job.SELF = Path(__file__).resolve()
job.BASE = 'explicit_trial_paired_campaign_20260924'
job.DESIGN = ROOT/'stage190_designs'/job.BASE/'design_01.json'
job.RUN = ROOT/'stage190_runs'/job.BASE/'run_01'
job.PREFLIGHT = ROOT/'stage190_runs'/job.BASE/'preflight_01'
job.OUT = ROOT/'stage190_evaluations'/job.BASE
job.WORK = qualification.job.WORK
job.PREFLIGHT_SCRIPT = job.SELF.with_name('qualify_audited_trial_campaign_v1.py')
job.kernel = new_kernel
api = job.api


def build_execute():
    source = inspect.getsource(historical.execute_segment)
    tree = ast.parse(source)
    contexts = records = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any('deadline.scope' in ast.unparse(x.context_expr) for x in node.items):
            node.items.append(ast.withitem(context_expr=ast.parse('observer.scope(parent.engine.runtime, True)',mode='eval').body,
                                          optional_vars=ast.Name(id='trial_log',ctx=ast.Store())))
            contexts += 1
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='record' for t in node.targets):
            node.value.keys.append(ast.Constant('contact_trial_trace'))
            node.value.values.append(ast.parse('copy.deepcopy(trial_log)',mode='eval').body)
            records += 1
    if (contexts, records) != (1, 1):
        raise RuntimeError('one observational scope and one raw field required')
    ast.fix_missing_locations(tree)
    job.__dict__['observer'] = observer
    namespace = dict(job.__dict__)
    exec(compile(tree, str(job.SELF)+'::observational_extension', 'exec'),namespace)
    identity = {'original_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
                'extended_ast_sha256':hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),
                'observer_scopes_added':1,'raw_fields_added':1,'other_ast_edits':0}
    return namespace['execute_segment'], identity


job.execute_segment, EXECUTE_IDENTITY = build_execute()
_verify = job.verify


def verify(d):
    _verify(d)
    qualification.job.verify(api.read(qualification.job.DESIGN))
    api.require(d['observer_structure'] == observer.STRUCTURAL_IDENTITY and d['audit_structure'] == new_kernel.STRUCTURAL_IDENTITY
                and d['execute_structure'] == EXECUTE_IDENTITY, 'frozen observational extension')


job.verify = verify


def prepare():
    historical.verify(api.read(historical.DESIGN))
    q = qualification.job
    q.verify(api.read(q.DESIGN))
    r = api.read(q.OUT/'results.json')
    api.require(r['passed'] and r['trajectory_steps_advanced']==0 and len(r['corruption_rejections'])==18, 'zero-step repair prerequisite')
    api.require(api.read(q.OUT/'completion.json')['results_sha256']==api.sha(q.OUT/'results.json'),'zero-step seal')
    api.verify_mapping(r['artifacts'])
    work=api.read(job.WORK)
    api.require(job.utc() < job.policy.utc(work['agent_work_end_utc']), 'work clock')
    # Reconstruct the verified predecessor with every original canonical seal.
    # This is a diagnostic seed only, never a fresh-production initial state.
    prefix = None; predecessor = None; inputs = {}
    name = 's2_i0_sphere_f0p03125'
    for index in range(1,138):
        p = historical.paths(historical.RUN,name,index)
        rec,prefix = job.codec.read_record(p['raw'],api.sha(historical.DESIGN),prefix)
        receipt=api.read(p['receipt'])
        api.require(receipt['status']=='independently_verified' and receipt['raw_sha256']==api.sha(p['raw']), 'verified diagnostic predecessor chain')
        for path in (p['raw'],p['raw'].with_suffix('.seal.json'),p['receipt']):inputs[str(path)]=api.sha(path)
        predecessor=rec['result']['checkpoint']
        if index%20==0:print('SEED_CHAIN_VERIFIED',index,flush=True)
    path=historical.paths(historical.RUN,name,138)['raw']
    oracle,_=job.codec.read_record(path,api.sha(historical.DESIGN),prefix)
    for p in (path,path.with_suffix('.seal.json')):inputs[str(p)]=api.sha(p)
    folder=job.DESIGN.parent;folder.mkdir(parents=True,exist_ok=False)
    seed=folder/'diagnostic_seed_01.json'
    api.write(seed,{'case':name,'checkpoint':predecessor,'oracle_path':str(path),
                    'oracle_rows':oracle['rows'],'oracle_state':oracle['result']['checkpoint']['state'],
                    'use':'Bounded diagnostic/restart qualification only; original failed tail not promoted.'},raw=True)
    d=copy.deepcopy(api.read(historical.DESIGN));d.pop('binding')
    for p in (historical.DESIGN,job.WORK,q.DESIGN,q.OUT/'results.json',q.OUT/'completion.json',seed):inputs[str(p)]=api.sha(p)
    d.update(stage='Stage190 fresh paired campaign with explicit trial provenance',
             sources=job.source_map(),inputs=inputs,agent_work_end_utc=work['agent_work_end_utc'],
             simulation_cutoff_utc=work['simulation_cutoff_utc'],final_audit_deadline_utc=work['final_audit_deadline_utc'],
             audit_source_sha256=api.sha(new_kernel.__file__),observer_structure=observer.STRUCTURAL_IDENTITY,
             audit_structure=new_kernel.STRUCTURAL_IDENTITY,execute_structure=EXECUTE_IDENTITY,
             diagnostic_seed=str(seed),qualification_total_steps=38200,
             claim='Original six labelled observations only after full fresh trajectory qualification. Stage187 remains failed; no population release or empirical validation claim.')
    d['preflight']['wall_seconds']=3600
    d['binding']=api.digest(d);api.write(job.DESIGN,d)
    verify(d);print('FROZEN',api.sha(job.DESIGN),flush=True)


if __name__=='__main__':
    args=sys.argv[1:]
    if args==['prepare']:prepare()
    elif len(args)==2 and args[0]=='supervise':job.supervise(args[1])
    elif len(args)==3 and args[0]=='worker':job.worker(args[1],args[2])
    elif len(args)==2 and args[0]=='auditor':job.auditor(args[1])
    elif len(args)==2 and args[0]=='evaluate':job.evaluate(args[1])
    else:raise ValueError('prepare | supervise MODE | worker MODE CASE | auditor MODE | evaluate MODE')
