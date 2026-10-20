"""Independent zero-step event-order and unchanged-verifier audit.

Does not import the qualification harness or DEM modules. Reconstructs entries
from sealed fixture artifacts and compares old/new acknowledgement behavior.
"""
from pathlib import Path
from types import SimpleNamespace
import ast, copy, hashlib, json, os, sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'stage185_staging')]
import campaign_lifecycle_policy_v1 as policy
import receipt_ack_single_pass_v1 as candidate

BASE = ROOT / 'stage204_evaluations/receipt_race_20260930'
QUAL = BASE / 'qualification_01'
OUT = BASE / 'independent_01'
DESIGN = ROOT / 'stage203_designs/autonomous_completion_20260929/design_01.json'
OLD = ROOT / 'stage187_staging/integrated_paired_campaign_v1.py'


def sha(path):
    d = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): d.update(chunk)
    return d.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check(ok, message):
    if not ok: raise AssertionError(message)


def publish(path, data):
    temp = path.with_name(path.name + f'.pending.{os.getpid()}')
    with temp.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.rename(temp, path)


class Boundary:
    def __init__(self, path, events): self.path, self.events, self.observed = path, iter(events), []
    def __fspath__(self): return str(self.path)
    def __str__(self): return str(self.path)
    def exists(self):
        value = next(self.events)
        self.observed.append(value)
        return value


def entry_from(folder, first=False):
    marker = read(folder / 'segment.ready.json')
    return dict(paths=dict(raw=folder / 'segment.json.xz', ready=folder / 'segment.ready.json',
                receipt=folder / 'segment.audit.json', trace=folder / 'segment.npy'), case='fixture',
                index=1 if first else 2, before_sha='b' * 64, previous_receipt_sha=None,
                previous_receipt_path=None if first else folder / 'parent.audit.json')


def old_from_ast(design_path, api):
    nodes = ast.parse(OLD.read_text(encoding='utf-8')).body
    functions = [n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == 'acknowledged']
    parent = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == 'receipt_parent')
    check(len(functions) == 2, 'old double-check structure')
    first = copy.deepcopy(functions[0]); first.name = '_acknowledged'
    env = dict(api=api, policy=policy, DESIGN=design_path)
    for n in (first, parent, functions[1]):
        exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(n)], type_ignores=[])), str(OLD), 'exec'), env)
    return env['acknowledged']


def main():
    q = read(QUAL / 'results.json')
    check(q['passed'] and q['new_trajectory_steps'] == 0, 'zero-step qualification passed')
    check(read(QUAL / 'completion.json')['results_sha256'] == sha(QUAL / 'results.json'), 'qualification seal')
    for path, digest in q['sources'].items(): check(sha(path) == digest, 'exact qualified sources')
    d = read(DESIGN)
    check(d['sources'][str(OLD)] == sha(OLD), 'preserved old campaign source')
    check(d['sources'][str(Path(policy.__file__))] == sha(policy.__file__), 'original verifier exact hash')
    check(d['numerical_gates'] == policy.GATES and not d['physical_changes'], 'original numerical and physical contract')
    syntax = ast.parse(Path(candidate.__file__).read_text(encoding='utf-8'))
    function = next(n for n in syntax.body if isinstance(n, ast.FunctionDef))
    calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
    check(sum(isinstance(n.func, ast.Attribute) and n.func.attr == 'exists' for n in calls) == 1, 'one existence decision')
    check(sum(isinstance(n.func, ast.Attribute) and n.func.attr == 'verify_receipt' for n in calls) == 1, 'original strict verifier still mandatory')
    allowed = {'exists', 'read', 'get', 'sha', 'verify_receipt', 'append'}
    check(all(not isinstance(n.func, ast.Attribute) or n.func.attr in allowed for n in calls), 'no writes or integration calls in helper')
    settings = dict(audit_source_sha256='c' * 64)
    api = SimpleNamespace(read=read, sha=sha)
    event_checks = []
    for first in (False, True):
        folder = QUAL / ('first' if first else 'successor'); dp = folder / 'design.json'
        for events in ((False, False), (False, True), (True, True)):
            e = entry_from(folder, first)
            b = Boundary(e['paths']['receipt'], events); e['paths']['receipt'] = b
            result = candidate.acknowledged(api, policy, dp, settings, [e])
            check(b.observed == [events[0]], 'single publication observation')
            check(result == ([] if events[0] else [e]), 'exact pending/available classification')
            if not events[0] and events[1]:
                check(candidate.acknowledged(api, policy, dp, settings, result) == [], 'published receipt accepted at next poll')
            old_entry = entry_from(folder, first)
            old_entry['paths']['receipt'] = Boundary(old_entry['paths']['receipt'], events)
            observed_failure = None
            try: old_result = old_from_ast(dp, api)(settings, [old_entry])
            except ValueError as exc: observed_failure = str(exc)
            expect_race = not first and events == (False, True)
            check((observed_failure == 'receipt/checkpoint ancestry') == expect_race, 'old race only when published between checks and parent exists')
            if not expect_race: check(old_result == ([] if events[1] else [old_entry]), 'stable original classification')
            event_checks.append(dict(first=first, observations=list(events), old_failure=observed_failure, repaired=True))
    rejected = []
    for folder in sorted(QUAL.glob('mutation_*')):
        e = entry_from(folder); dp = folder / 'design.json'
        errors = []
        for name, call in [('old', lambda: old_from_ast(dp, api)(settings, [e])),
                           ('new', lambda: candidate.acknowledged(api, policy, dp, settings, [e]))]:
            try: call()
            except (ValueError, RuntimeError) as exc: errors.append(dict(route=name, error=repr(exc)))
        check(len(errors) == 2, 'both versions reject fixture corruption')
        rejected.append(dict(fixture=str(folder), errors=errors))
    check(len(rejected) == 17, 'complete corruption inventory')
    OUT.mkdir(parents=True, exist_ok=False)
    result = dict(passed=True, new_trajectory_steps=0, utc=datetime.now(timezone.utc).isoformat(),
                  qualified_result_sha256=sha(QUAL / 'results.json'), original_verifier_sha256=sha(policy.__file__),
                  candidate_sha256=sha(candidate.__file__), source_sha256=sha(__file__),
                  publication_event_checks=event_checks, corruptions_rejected_by_both=rejected,
                  physical_changes=[], old_runtime_interleaving_recorded=False,
                  future_campaign_requires_new_frozen_integration_proof=True)
    publish(OUT / 'results.json', result)
    publish(OUT / 'completion.json', dict(passed=True, results_sha256=sha(OUT / 'results.json')))
    print(json.dumps(dict(passed=True, event_checks=len(event_checks), mutation_checks=len(rejected), new_trajectory_steps=0)), flush=True)


if __name__ == '__main__': main()
