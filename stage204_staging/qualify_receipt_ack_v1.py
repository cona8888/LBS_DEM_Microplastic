"""Zero-step race reproduction, strict mutation tests, and failed-run inventory.

Imports only the immutable lightweight lifecycle policy, not any DEM engine.
Old acknowledgement functions are extracted with AST, preserving their code.
The inventory is metadata/compressed-artifact verification, not a raw physics
re-audit or permission to resume the failed Stage203 campaign.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import ast, copy, hashlib, json, os, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage185_staging'))
import campaign_lifecycle_policy_v1 as policy
import receipt_ack_single_pass_v1 as candidate

BASE = ROOT / 'stage204_evaluations/receipt_race_20260930'
CONTRACT = ROOT / 'stage204_designs/receipt_race_20260930/contract_01.json'
DESIGN = ROOT / 'stage203_designs/autonomous_completion_20260929/design_01.json'
OLD = ROOT / 'stage187_staging/integrated_paired_campaign_v1.py'
RUN = Path('D:/MATDEM_MICROPLASTIC/stage203_runs/autonomous_completion_20260929/run_01')
EXPECTED = '6aa736ee9eb0e2ba797045086798aa0564d98446f896b8c3d56fc5223a4baa37'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def publish(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.pending.{os.getpid()}')
    if path.exists() or temp.exists():
        raise FileExistsError(str(path))
    with temp.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.rename(temp, path)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def finish(folder, result):
    result.update(utc=datetime.now(timezone.utc).isoformat(), new_trajectory_steps=0,
                  contract_sha256=sha(CONTRACT), sources={str(p): sha(p) for p in
                  (Path(__file__), Path(candidate.__file__), Path(policy.__file__), OLD)})
    publish(folder / 'results.json', result)
    publish(folder / 'completion.json', dict(passed=result['passed'], results_sha256=sha(folder / 'results.json')))
    print(json.dumps({k: result[k] for k in ('passed', 'utc', 'new_trajectory_steps')}, indent=2), flush=True)


def old_acknowledgers(design_path, api):
    tree = ast.parse(OLD.read_text(encoding='utf-8'))
    nodes = [copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ('acknowledged', 'receipt_parent')]
    require(len(nodes) == 3, 'two old acknowledgement definitions and parent helper')
    nodes[0].name = '_old_base'
    env = dict(api=api, policy=policy, DESIGN=design_path)
    for node in nodes:
        if node.name == 'acknowledged':
            env['_acknowledged'] = env['_old_base']
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(OLD), 'exec'), env)
    return env['acknowledged']


class PublicationBoundary:
    """Deterministic observations: absent, then immutable file published."""
    def __init__(self, path, observations):
        self.path, self.observations, self.calls = path, list(observations), 0
    def __fspath__(self): return str(self.path)
    def __str__(self): return str(self.path)
    def exists(self):
        index = min(self.calls, len(self.observations) - 1)
        self.calls += 1
        return self.observations[index]


def fixture(folder, mutation=None, first=False):
    folder.mkdir(parents=True, exist_ok=False)
    design_path = folder / 'design.json'; publish(design_path, {'fixture': True})
    parent_path = folder / 'parent.audit.json'; publish(parent_path, {'parent': True})
    paths = {key: folder / name for key, name in dict(raw='segment.json.xz', ready='segment.ready.json',
             receipt='segment.audit.json', trace='segment.npy').items()}
    paths['raw'].write_bytes(b'fixture raw, no trajectory')
    paths['raw'].with_suffix('.seal.json').write_bytes(b'fixture seal')
    paths['trace'].write_bytes(b'fixture trace, no trajectory')
    marker = dict(case='fixture', segment=1 if first else 2, design_sha256=sha(design_path),
                  raw_path=str(paths['raw']), raw_sha256=sha(paths['raw']),
                  seal_sha256=sha(paths['raw'].with_suffix('.seal.json')),
                  input_checkpoint_sha256='b' * 64, steps=10)
    receipt = dict(case='fixture', segment=marker['segment'], design_sha256=sha(design_path),
                   audit_source_sha256='c' * 64, trace_path=str(paths['trace']),
                   raw_sha256=marker['raw_sha256'], trace_sha256=sha(paths['trace']),
                   previous_receipt_sha256=None if first else sha(parent_path),
                   input_checkpoint_sha256=marker['input_checkpoint_sha256'],
                   status='independently_verified', summary=dict(passed=True, steps=10, start_s=0., stop_s=1.,
                   status='paused_checkpoint', complete_observation=False))
    if mutation:
        target, field, value = mutation
        if target == 'summary': receipt['summary'][field] = value
        elif target == 'receipt': receipt[field] = value
        elif target == 'marker': marker[field] = value
    publish(paths['ready'], marker); receipt['ready_sha256'] = sha(paths['ready'])
    publish(paths['receipt'], receipt)
    entry = dict(paths=paths, case='fixture', index=marker['segment'], before_sha='b' * 64,
                 previous_receipt_sha=None, previous_receipt_path=None if first else parent_path)
    return design_path, {'audit_source_sha256': 'c' * 64}, entry


def tests():
    require(sha(DESIGN) == EXPECTED, 'old design identity')
    d = read(DESIGN)
    require(d['sources'][str(OLD)] == sha(OLD), 'old code exact frozen version')
    require(d['sources'][str(Path(policy.__file__))] == sha(policy.__file__), 'original verifier unchanged')
    folder = BASE / 'qualification_01'; folder.mkdir(parents=True, exist_ok=False)
    api = SimpleNamespace(read=read, sha=sha)
    dp, settings, entry = fixture(folder / 'race')
    old = old_acknowledgers(dp, api)
    entry['paths']['receipt'] = PublicationBoundary(entry['paths']['receipt'], [False, True])
    failure = None
    try: old(settings, [entry])
    except ValueError as error: failure = str(error)
    require(failure == 'receipt/checkpoint ancestry', 'original double-check race reproduced')
    entry['paths']['receipt'] = PublicationBoundary(Path(os.fspath(entry['paths']['receipt'])), [False, True])
    left = candidate.acknowledged(api, policy, dp, settings, [entry])
    require(left == [entry] and entry['paths']['receipt'].calls == 1, 'one absence decision remains pending')
    require(candidate.acknowledged(api, policy, dp, settings, left) == [], 'next poll accepts exact immutable lineage')
    controls = []
    for first in (False, True):
        dp, settings, e = fixture(folder / ('first' if first else 'successor'), first=first)
        require(candidate.acknowledged(api, policy, dp, settings, [e]) == [], 'valid receipt accepted')
        require(old_acknowledgers(dp, api)(settings, [e]) == [], 'old/new stable publication equivalence')
        controls.append(dict(first=first, stable_identity=True))
    mutations = [
        ('receipt', 'previous_receipt_sha256', '0' * 64),
        ('receipt', 'input_checkpoint_sha256', '0' * 64),
        ('receipt', 'design_sha256', '0' * 64),
        ('receipt', 'audit_source_sha256', '0' * 64),
        ('receipt', 'raw_sha256', '0' * 64),
        ('receipt', 'trace_sha256', '0' * 64),
        ('receipt', 'status', 'audit_failed'),
        ('receipt', 'trace_path', 'unexpected.npy'),
        ('marker', 'input_checkpoint_sha256', '0' * 64),
        ('marker', 'raw_sha256', '0' * 64),
        ('marker', 'seal_sha256', '0' * 64),
        ('summary', 'passed', False),
        ('summary', 'steps', 9),
        ('summary', 'start_s', 1.),
        ('summary', 'stop_s', float('nan')),
        ('summary', 'status', 'invented_complete'),
        ('summary', 'complete_observation', True),
    ]
    rejected = []
    for index, mutation in enumerate(mutations):
        dp, settings, e = fixture(folder / f'mutation_{index:02d}', mutation)
        error = None
        try: candidate.acknowledged(api, policy, dp, settings, [e])
        except (ValueError, RuntimeError) as exc: error = repr(exc)
        require(error is not None, 'corruption rejected ' + str(mutation))
        rejected.append(dict(mutation=str(mutation), error=error))
    dp, settings, e = fixture(folder / 'missing_parent')
    e['previous_receipt_path'] = folder / 'never_published.audit.json'
    try: candidate.acknowledged(api, policy, dp, settings, [e])
    except FileNotFoundError: missing_rejected = True
    else: missing_rejected = False
    require(missing_rejected, 'present child with missing predecessor fails closed')
    finish(folder, dict(passed=True, old_race_error=failure, stable_controls=controls,
                       rejected_mutations=rejected, missing_parent_rejected=True,
                       runtime_interleaving_directly_captured=False, physical_changes=[],
                       publication_claim='Reproduced software race consistent with observed failure; full failed-run audit remains separate.'))


def inventory():
    require(sha(DESIGN) == EXPECTED, 'old design identity')
    terminal = read(RUN / 'completion.json')
    require(terminal['all_owned_processes_retired'] and terminal['design_sha256'] == EXPECTED, 'retired old campaign')
    d = read(DESIGN); folder = BASE / 'failed_inventory_01'; folder.mkdir(parents=True, exist_ok=False)
    for mapping in (d['sources'], d['inputs']):
        for path, expected in mapping.items(): require(sha(path) == expected, 'old frozen lineage ' + path)
    cases = []; total_steps = 0; total_records = 0
    for case in d['cases']:
        name = case['id']; base = RUN / name; markers = sorted(base.glob('segment_*.ready.json'))
        previous = None; stop = 0.; steps = 0; chain = []
        for index, marker_path in enumerate(markers, 1):
            stem = f'segment_{index:05d}'
            require(marker_path.name == stem + '.ready.json', 'contiguous ready chain')
            paths = {key: base / (stem + ext) for key, ext in dict(raw='.json.xz', ready='.ready.json', receipt='.audit.json', trace='.npy').items()}
            marker, receipt = read(marker_path), read(paths['receipt'])
            summary = receipt['summary']
            require(receipt['previous_receipt_sha256'] == previous, 'independent predecessor receipt hash')
            require(receipt['input_checkpoint_sha256'] == marker['input_checkpoint_sha256'], 'marker/receipt checkpoint identity')
            require(summary['start_s'] == stop and summary['stop_s'] <= case['spec']['horizon_s'], 'complete exact prefix clock')
            policy.verify_receipt(paths, name, index, EXPECTED, d['audit_source_sha256'], marker['input_checkpoint_sha256'], previous)
            previous = sha(paths['receipt']); stop = summary['stop_s']; steps += marker['steps']
            chain.append(dict(segment=index, receipt_sha256=previous, ready_sha256=sha(marker_path), raw_sha256=sha(paths['raw']), stop_s=stop))
        require(len(list(base.glob('segment_*.json.xz'))) == len(markers), 'no unannounced raw archives')
        total_steps += steps; total_records += len(chain)
        cases.append(dict(case=name, segments=len(chain), receipt_verified_steps=steps, last_verified_time_s=stop, chain=chain,
                          complete_observation=False, producer_completion_present=(base / 'completion.json').exists()))
    finish(folder, dict(passed=True, failed_campaign_remains_failed=True, terminal=terminal,
                       total_records=total_records, receipt_verified_steps=total_steps, cases=cases,
                       all_frozen_sources_and_inputs_verified=True, full_uncompressed_history_audit=False,
                       inference='Committed receipt and artifact ancestry is consistent; live double-check interleaving was not recorded.'))


if __name__ == '__main__':
    {'tests': tests, 'inventory': inventory}[sys.argv[1]]()
