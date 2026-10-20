"""Independent full-stack metadata-repair binding and resource qualification.

No trajectory is run. Original numerical qualification is explicitly reused.
Dynamic receipt controls use fixture-only dependency injection into an exact
copy of the producer adapter's bytecode; production globals are not modified.
"""
from pathlib import Path
from types import FunctionType, SimpleNamespace
import copy, itertools, os, sys, shutil
import receipt_repaired_campaign_v1 as s

api, job = s.api, s.job
PREP = job.OUT / 'preparation_binding_01/results.json'
FIXTURES = s.ROOT / 'stage204_evaluations/receipt_race_20260930/qualification_01'


class Boundary:
    def __init__(self, path, events): self.path, self.events, self.calls = path, iter(events), 0
    def __str__(self): return str(self.path)
    def __fspath__(self): return str(self.path)
    def exists(self): self.calls += 1; return next(self.events)


def fixture_entry(folder, first=False):
    return dict(case='fixture', index=1 if first else 2, before_sha='b' * 64,
                previous_receipt_sha=None, previous_receipt_path=None if first else folder / 'parent.audit.json',
                paths=dict(raw=folder / 'segment.json.xz', ready=folder / 'segment.ready.json',
                           receipt=folder / 'segment.audit.json', trace=folder / 'segment.npy'))


def binding_checks():
    # The original worker looks this function up in its own real globals.
    actual = job.worker.__globals__['acknowledged']
    api.require(actual is s.acknowledged and actual.__globals__['ack'] is s.ack, 'real producer callback routing')
    for name in s.old.IDENTICAL:
        if name == 'acknowledged': continue
        api.require(getattr(job, name).__code__ == getattr(s.pre.job, name).__code__, 'unchanged executable lifecycle ' + name)
    api.require(s.raw_execute.__code__ == s.pre.raw_execute.__code__ and job.execute_segment.__code__ == s.pre.execute_segment.__code__, 'integration and contact route exact bytecode')
    api.require(s.raw_execute.__globals__['DESIGN'] == job.DESIGN and job.execute_segment.__globals__['raw_execute'] is s.raw_execute, 'new raw identity and correct contact-wrapper binding')
    for key in ('parent', 'fast', 'prior', 'deadline', 'capture', 'observer'):
        api.require(s.raw_execute.__globals__[key] is s.pre.raw_execute.__globals__[key], 'physics namespace identity ' + key)
    events = []
    for first in (False, True):
        folder = FIXTURES / ('first' if first else 'successor')
        injected_job = SimpleNamespace(policy=job.policy, DESIGN=folder / 'design.json')
        adapter = FunctionType(actual.__code__, dict(actual.__globals__, job=injected_job),
                               actual.__name__, actual.__defaults__, actual.__closure__)
        api.require(s.q.campaign.code_sha(adapter) == s.q.campaign.code_sha(actual), 'fixture and real adapter exact code')
        for observations in ((False, False), (False, True), (True, True)):
            entry = fixture_entry(folder, first)
            boundary = Boundary(entry['paths']['receipt'], observations); entry['paths']['receipt'] = boundary
            pending = adapter(dict(audit_source_sha256='c' * 64), [entry])
            api.require(boundary.calls == 1 and pending == ([] if observations[0] else [entry]), 'bound adapter uses one exact availability decision')
            if observations == (False, True):
                api.require(adapter(dict(audit_source_sha256='c' * 64), pending) == [] and boundary.calls == 2, 'delayed receipt accepted on next invocation')
            events.append(dict(first_receipt=first, visibility=list(observations), passed=True))
    for folder in sorted(FIXTURES.glob('mutation_*')):
        injection = SimpleNamespace(policy=job.policy, DESIGN=folder / 'design.json')
        adapter = FunctionType(actual.__code__, dict(actual.__globals__, job=injection), actual.__name__, actual.__defaults__, actual.__closure__)
        try: adapter(dict(audit_source_sha256='c' * 64), [fixture_entry(folder)])
        except (ValueError, RuntimeError): pass
        else: raise AssertionError('bound adapter accepted corrupted fixture ' + str(folder))
    api.require(job.DESIGN == s.ROOT / 'stage205_designs' / s.BASE / 'design_01.json' and
                actual.__globals__['job'] is job, 'production namespace unchanged by fixture tests')
    return dict(passed=True, producer_binding_events=events, corrupt_bound_adapter_fixtures=17,
                scientific_bindings=s.bindings(), physical_changes=[], new_trajectory_steps=0)


def preparation():
    result = binding_checks()
    result.update(utc=job.utc().isoformat(), source_sha256=api.sha(__file__), launcher_sha256=api.sha(s.__file__),
                  authority_sha256=api.sha(job.WORK), original_design_sha256=api.sha(s.OLD_DESIGN),
                  repair_result_sha256=api.sha(s.REPAIR), qualification_inheritance=s.old.qualification_lineage())
    job.commit(PREP, result); job.commit(PREP.parent / 'completion.json', dict(passed=True, results_sha256=api.sha(PREP)))
    print('BOUND_ADAPTER_PASS', api.sha(PREP), flush=True)


def campaign():
    d = api.read(job.DESIGN); job.verify(d); s.old_terminal()
    previous = api.read(s.OLD_DESIGN); authority = api.read(job.WORK); r = s.sealed(s.RESOURCE)
    prereq = s.sealed(PREP); bridge = s.sealed(s.BRIDGE)
    api.require(prereq['passed'] and prereq['launcher_sha256'] == api.sha(s.__file__) and prereq['source_sha256'] == api.sha(__file__), 'exact prior independent binding proof')
    unchanged = set(previous) - (s.old.ALLOWED | {'receipt_acknowledgement_repair'})
    api.require(all(d[k] == previous[k] for k in unchanged), 'all original scientific and budget fields preserved')
    original_cost = s.sealed(s.old.OLD_RESOURCE); independently_checked_cost = s.sealed(s.old.OLD_RESOURCE_AUDIT)
    api.require(r['hours_with_margin'] == original_cost['production_hours_with_margin'] == independently_checked_cost['required_production_hours'] and
                r['bytes_with_margin'] == original_cost['storage_bytes_with_margin'] and
                r['required_final_audit_hours'] == independently_checked_cost['required_final_audit_hours'], 'same conservative measured costs')
    for key in ('samples', 'cases', 'shape_costs', 'late_history_cost', 'queue', 'schedule_tests', 'call_limit_passed'):
        api.require(r[key] == original_cost[key], 'unchanged complete resource evidence ' + key)
    available = (job.policy.utc(authority['simulation_cutoff_utc']) - job.utc()).total_seconds() / 3600
    reserve = (job.policy.utc(authority['final_audit_deadline_utc']) - job.policy.utc(authority['simulation_cutoff_utc'])).total_seconds() / 3600
    free = shutil.disk_usage(job.ROOT).free
    api.require(available >= r['hours_with_margin'] and reserve >= r['required_final_audit_hours'] and free >= independently_checked_cost['storage_with_reserve_bytes'], 'independent current calendar and storage arithmetic')
    reject_labels = []
    mutations = [('case', lambda x: x['cases'].pop()), ('step_cap', lambda x: x['budget'].update(step_cap_per_call=20000)),
                 ('gate', lambda x: x['numerical_gates'].update(whole_position_over_b_max=.1)), ('concurrency', lambda x: x['budget'].update(workers=6)),
                 ('old_source', lambda x: x['sources'].pop(next(iter(previous['sources'])))),
                 ('helper', lambda x: x['receipt_acknowledgement_repair'].update(candidate_sha256='0' * 64)),
                 ('horizon', lambda x: x['cases'][0]['spec'].update(horizon_s=1.))]
    for label, change in mutations:
        bad = copy.deepcopy(d); change(bad)
        try: s.equivalence(bad)
        except (ValueError, RuntimeError, AssertionError): reject_labels.append(label)
        else: raise AssertionError('corrupt amendment accepted ' + label)
    checks = 0
    order = [case['id'] for case in d['cases']]
    for retirement_order in itertools.permutations(order):
        life = job.policy.initial(order); remaining = list(retirement_order)
        while life.queued or life.active:
            while True:
                life, name = job.policy.dispatch(life, 3, True)
                if name is None: break
                api.require(len(life.active) * 2 <= 6, 'original global-six dispatch invariant')
            name = next(n for n in remaining if n in life.active); remaining.remove(name)
            life = job.policy.retire(life, name, 0, True)
        api.require(len(life.retired) == 6 and not life.stop_reasons, 'all original cases dispatched and retired')
        checks += 1
    api.require(not job.RUN.exists() and not s.old.active_owned(), 'no existing simulation or evaluator before fresh campaign')
    dynamic = binding_checks()
    api.require(bridge['bindings'] == dynamic['scientific_bindings'] and bridge['new_trajectory_steps'] == 0, 'same final executable bridge')
    inputs = [job.DESIGN, job.WORK, s.BRIDGE, PREP, s.REPAIR, s.INVENTORY, s.OLD_EVAL, s.RESOURCE, Path(__file__)]
    result = dict(passed=True, new_trajectory_steps=0, design_sha256=api.sha(job.DESIGN), source_sha256=api.sha(__file__),
                  required_production_hours=r['hours_with_margin'], available_production_hours=available,
                  required_final_audit_hours=r['required_final_audit_hours'], available_final_audit_hours=reserve,
                  storage_with_reserve_bytes=independently_checked_cost['storage_with_reserve_bytes'], free_D_bytes=free,
                  zero_step_dispatch_permutations=checks, corrupt_amendments_rejected=reject_labels,
                  bound_adapter_proof=dynamic, old_campaign_remains_failed=True, utc=job.utc().isoformat(),
                  inputs={str(p): api.sha(p) for p in inputs})
    job.commit(s.INDEPENDENT, result); job.commit(s.INDEPENDENT.parent / 'completion.json', dict(passed=True, results_sha256=api.sha(s.INDEPENDENT)))
    print('INDEPENDENT_REPAIRED_BRIDGE_PASS', api.sha(job.DESIGN), flush=True)


if __name__ == '__main__':
    {'bindings': preparation, 'campaign': campaign}[sys.argv[1]]()
