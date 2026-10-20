"""Isolated Paper1 administration around the unchanged admitted transport stack."""
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
from contextlib import contextmanager
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage245_staging'), str(ROOT/'paper1_staging')]
import continue_guard_v3 as qualified
import immutable_field_scope_v1 as fields
api = qualified.api


def clone(fn, namespace):
    return FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)


def build(plan_path, authorization_path, physical_design_path, admin, verify_inputs):
    """No solve here; returned transaction retains original independent auditor."""
    source_job = qualified.job
    job = ModuleType('_paper1_private_transport')
    job.__dict__.update(vars(qualified.private_job))
    job.DESIGN = Path(physical_design_path)
    for name, fn in vars(source_job).items():
        if isinstance(fn, FunctionType) and fn.__globals__ is vars(source_job):
            setattr(job, name, clone(fn, vars(job)))
    @contextmanager
    def field_scope(api, metadata):
        with fields.scope(api, (2, metadata['flow_factor'], metadata['cpd']), metadata) as snap:
            yield snap
    job.prior = SimpleNamespace(**{**vars(source_job.prior), 'snapshot': SimpleNamespace(scope=field_scope)})
    observation = contextmanager(clone(qualified.observation.__wrapped__,
        {**qualified.observation.__wrapped__.__globals__, 'c': admin, 'job': job}))
    job.observer = SimpleNamespace(**{**vars(qualified.observer), 'scope': observation})
    raw = clone(qualified.raw, vars(job))
    frozen = SimpleNamespace(**{**vars(qualified.frozen), 'raw_execute': raw})
    execute = clone(qualified.execute, {**qualified.execute.__globals__, 'job': job, 'frozen': frozen})
    inner = clone(qualified.baseline.inner, {**qualified.baseline.inner.__globals__, 'job': job})
    kernel = clone(qualified.baseline.kernel, {**qualified.baseline.kernel.__globals__, '_kernel': inner})
    baseline = SimpleNamespace(**{**vars(qualified.baseline), 'execute': execute, 'inner': inner, 'kernel': kernel})
    original_segment = qualified.private['segment']
    segment = clone(original_segment, {**original_segment.__globals__, 'job': job, 'baseline': baseline,
        'c': admin, 'PLAN': Path(plan_path), 'AUTH': Path(authorization_path), 'verify_scientific_inputs': verify_inputs})
    api.require(raw.__code__ is qualified.raw.__code__ and execute.__code__ is qualified.execute.__code__
                and inner.__code__ is qualified.baseline.inner.__code__
                and kernel.__code__ is qualified.baseline.kernel.__code__
                and segment.__code__ is original_segment.__code__, 'Original production and auditor code objects')
    for name in ('parent', 'fast', 'deadline', 'capture'):
        api.require(raw.__globals__[name] is qualified.raw.__globals__[name], 'Original physical dependency: '+name)
    api.require(job.prior.p is source_job.prior.p and job.prior.candidate is source_job.prior.candidate
                and job.WORK == source_job.WORK and job.parent is source_job.parent,
                'Original integration, clearance, numerical-policy and contact dependencies')
    api.require(kernel.__globals__['_kernel'] is inner and inner.__globals__['job'] is job
                and segment.__globals__['job'] is job and raw.__globals__['observer'] is job.observer,
                'Actual producer/auditor/observer association')
    def geometry_for(case):
        spec = case['spec']
        with field_scope(api, spec['field_metadata']):
            _, data, metadata = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
        return api.frozen.h.geometry_exact_v1.GrainGeometry(
            data['sand_centres_m'], data['sand_radii_m'], metadata['cell_length_m'])
    return SimpleNamespace(job=job, raw=raw, execute=execute, baseline=baseline,
                           segment=segment, geometry_for=geometry_for, observation=observation)
