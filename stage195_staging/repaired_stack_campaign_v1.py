"""Isolated Stage195 qualification instance; production deliberately disabled.

Original lifecycle and integration bytecode are retained. Stage194's qualified
stateless solve wraps the integration call; lossless codec and route auditor
are explicitly bound. A different future authorization/design is required to
launch production, especially while the approved deadline does not fit.
"""
from pathlib import Path
from types import FunctionType, SimpleNamespace
import copy
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage194_staging'))
import qualify_failure_codec_v1 as q
import early_semismooth_dispatch_v1 as repair
import audit_early_semismooth_v1 as repaired_audit
frozen, api = q.job, q.api
spec = importlib.util.spec_from_file_location('_stage195_isolated_lifecycle', q.campaign.qualified.instance.historical.__file__)
job = importlib.util.module_from_spec(spec); sys.modules[spec.name] = job; spec.loader.exec_module(job)
job.SELF = Path(__file__).resolve()
job.BASE = 'repaired_stack_preflight_20260925'
job.DESIGN = ROOT/'stage195_designs'/job.BASE/'design_01.json'
job.WORK = job.DESIGN.with_name('authorization_01.json')
job.RUN = ROOT/'stage195_runs'/job.BASE/'production_not_authorized'
job.PREFLIGHT = ROOT/'stage195_runs'/job.BASE/'preflight_01'
job.OUT = ROOT/'stage195_evaluations'/job.BASE
job.PREFLIGHT_SCRIPT = Path(__file__).with_name('qualify_repaired_stack_v1.py')
job.codec = q.repair.codec
job.kernel = SimpleNamespace(evaluate=repaired_audit.kernel)
job.observer = frozen.observer
_base_verify = job.verify
raw_execute = FunctionType(frozen.execute_segment.__code__, dict(job.__dict__), 'execute_segment', frozen.execute_segment.__defaults__, frozen.execute_segment.__closure__)


def execute_segment(d, case, before, raw_path, cap, prefix, stop_utc):
    with repair.scope(job.parent.engine.runtime, True, job.policy.utc(stop_utc).timestamp()):
        return raw_execute(d, case, before, raw_path, cap, prefix, stop_utc)


job.execute_segment = execute_segment


def verify(d):
    _base_verify(d)
    old = api.read(frozen.DESIGN); frozen.verify(old)
    w = api.read(job.WORK)
    api.require(d['cases'] == old['cases'] and d['numerical_gates'] == old['numerical_gates'] and d['budget'] == old['budget'], 'unchanged scientific design and resource caps')
    api.require(w['maximum_new_accepted_trajectory_steps'] == 18200 and w['maximum_concurrent_simulation_workers'] == 3, 'bounded renewed preflight authority')
    api.require(not d['production_authorized'] and not w['production_launch_allowed_by_this_preflight_design'], 'preflight cannot authorize production')
    api.require(d['codec_schema'] == q.repair.SCHEMA and d['audit_structure'] == repaired_audit.STRUCTURAL_IDENTITY, 'exact repaired evidence stack')
    api.require(d['integration_code_sha256'] == q.campaign.code_sha(raw_execute) == q.campaign.code_sha(frozen.execute_segment), 'identical integration code')
    api.require(raw_execute.__code__ is frozen.execute_segment.__code__, 'same integration code object')
    for key in ('parent', 'fast', 'prior', 'deadline', 'capture', 'observer'):
        api.require(raw_execute.__globals__[key] is getattr(frozen, key), 'same frozen runtime module '+key)
    api.require(raw_execute.__globals__['DESIGN'] == job.DESIGN and raw_execute.__globals__['codec'] is q.repair.codec, 'explicit output and codec bindings')
    api.require(d['prior_stage194_steps'] == 40589 and d['preflight']['maximum_new_steps'] == 18200, 'separate exact step ledgers')


job.verify = verify


def prepare():
    old = api.read(frozen.DESIGN); frozen.verify(old)
    work = api.read(job.WORK)
    api.require(job.utc() < job.policy.utc(work['agent_work_end_utc']), 'preflight preparation clock')
    base = ROOT/'stage194_evaluations/evidence_repair_20260924'
    readiness = base/'repair_readiness_01/results.json'; r = api.read(readiness)
    api.require(api.sha(readiness) == '20e05b087c4196f84a5f127acf1e179384b210710e406e9b5ae8f802b53a66ce', 'frozen repair handoff')
    api.require(r['numerical_repair_and_local_verification_passed'] and r['window_new_steps'] == 40589, 'local qualification prerequisite')
    api.verify_mapping(r['inputs']); api.verify_mapping(r['sources'])
    d = copy.deepcopy(old); d.pop('binding')
    paths = [job.WORK, frozen.DESIGN, readiness, readiness.parent/'completion.json',
             base/'broader_early_dispatch_independent_02/results.json', base/'broader_early_dispatch_independent_02/completion.json',
             ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json',
             ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_01.json.xz',
             ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_01.json.seal.json',
             ROOT/'stage194_designs/evidence_repair_20260924/early_semismooth_restart_01.json',
             ROOT/'stage194_runs/evidence_repair_20260924/early_semismooth_restart_01/call_01.json.xz',
             ROOT/'stage194_runs/evidence_repair_20260924/early_semismooth_restart_01/call_01.json.seal.json']
    sources = dict(d['sources'])
    for path in list((ROOT/'stage194_staging').glob('*.py'))+list(Path(__file__).parent.glob('*.py')): sources[str(path)] = api.sha(path)
    inputs = {**d['inputs'], **{str(path): api.sha(path) for path in paths}}
    ratio = max(1., max(x['transaction_ratio'] for x in r['archived_cost_comparisons']))
    storage = max(1., max(x['storage_ratio'] for x in r['archived_cost_comparisons']))
    d.update(stage='Stage195 repaired-stack full numerical/process preflight', sources=sources, inputs=inputs,
        agent_work_end_utc=work['agent_work_end_utc'], codec_schema=q.repair.SCHEMA,
        audit_source_sha256=api.sha(repaired_audit.__file__), audit_structure=repaired_audit.STRUCTURAL_IDENTITY,
        integration_code_sha256=q.campaign.code_sha(raw_execute), prior_stage194_steps=40589,
        provenance_transaction_hours_with_margin=r['runtime_gate_floor_hours_not_new_forecast']*ratio,
        provenance_bytes_with_margin=int(old['provenance_bytes_with_margin']*storage+1),
        repaired_cost_scaling={'transaction_factor':ratio,'storage_factor':storage,'limitation':'Conservative short-sample scheduling scenario, not a guaranteed full-path bound.'},
        production_authorized=False,
        preflight={'maximum_new_steps':18200,'wall_seconds':3600,'steps_per_live_segment':500,'segments_per_live_case':2,'contact_probe_steps':1000},
        stress_case='s2_i0_fibre_f0p0625',
        qualification_inheritance=None,
        claim='New bounded repaired-stack verification only. Two labelled placements remain incomplete; no population release or empirical validation. No production launch under this design.')
    # Explicit named paths avoid positional assumptions when binding the stress fixture.
    d['stress_seed_design'] = str(ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json')
    d['stress_seed_raw'] = str(ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_01.json.xz')
    d['stress_oracle_design'] = str(ROOT/'stage194_designs/evidence_repair_20260924/early_semismooth_restart_01.json')
    d['stress_oracle_raw'] = str(ROOT/'stage194_runs/evidence_repair_20260924/early_semismooth_restart_01/call_01.json.xz')
    d['binding'] = api.digest(d); job.commit(job.DESIGN, d); verify(d)
    print('STAGE195_FROZEN', api.sha(job.DESIGN), 'scenario_hours', d['provenance_transaction_hours_with_margin'], flush=True)


def guard(mode):
    api.require(mode == 'preflight', 'production disabled pending revised deadline and separate authorization/design')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['prepare']: prepare()
    elif len(args) == 2 and args[0] in ('supervise', 'auditor', 'evaluate'):
        guard(args[1]); getattr(job, args[0])(args[1])
    elif len(args) == 3 and args[0] == 'worker':
        guard(args[1]); job.worker(args[1], args[2])
    else: raise ValueError('prepare | supervise preflight | auditor preflight | evaluate preflight | worker preflight CASE')
