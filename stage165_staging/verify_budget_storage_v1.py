"""CPU-light tests only: no particle integration or active-run mutation."""
from pathlib import Path
import gzip
import inspect
import json
import sys
import transport_budget_io_v1 as io

api = io.api
ROOT = io.ROOT
OUT = ROOT / 'stage165_evaluations/budget_storage_units_20260922/verification_01'


def run():
    source = io.qualification.RUN / 'engagement/factor_0.0625/segment_01.json'
    record = io.qualification.read(source)
    OUT.mkdir(parents=True, exist_ok=False)
    original = io.modal.CANDIDATE
    base = inspect.signature(original)
    for ceiling in [1, 500000, 10000000, 50000000]:
        altered = io.with_step_budget(original, ceiling)
        assert altered.__code__ is original.__code__
        assert altered.__globals__ is original.__globals__
        sig = inspect.signature(altered)
        assert sig.parameters['max_steps'].default == ceiling
        assert all(base.parameters[k] == sig.parameters[k] for k in base.parameters if k != 'max_steps')
    rejects = []
    for bad in [0, -1, True, 1.5, '500000', 50000001]:
        try:
            io.with_step_budget(original, bad)
        except ValueError:
            rejects.append(str(bad))
        else:
            raise AssertionError('invalid step budget accepted')
    a, b = OUT / 'roundtrip_a.json.gz', OUT / 'roundtrip_b.json.gz'
    seal = io.write_record(a, record)
    io.write_record(b, record)
    assert a.read_bytes() == b.read_bytes(), 'deterministic gzip bytes'
    restored = io.read_record(a, record['design_sha256'])
    assert api.digest(restored) == api.digest(record), 'unrounded full-state/data identity'
    with gzip.open(a, 'rb') as f:
        raw = f.read()
    assert json.loads(raw) == record, 'independent gzip/JSON round-trip'
    previous = api.sha(a)
    try:
        io.write_record(a, record)
    except FileExistsError:
        pass
    else:
        raise AssertionError('overwrite accepted')
    assert api.sha(a) == previous, 'failed overwrite modified artifact'
    try:
        io.read_record(a, 'incorrect_design')
    except RuntimeError:
        pass
    else:
        raise AssertionError('wrong design accepted')
    broken = OUT / 'corrupted.json.gz'
    altered = bytearray(a.read_bytes()); altered[len(altered)//2] ^= 1
    with broken.open('xb') as f:
        f.write(altered)
    api.write(broken.with_suffix('.seal.json'), seal)
    try:
        io.read_record(broken, record['design_sha256'])
    except RuntimeError:
        pass
    else:
        raise AssertionError('corrupt data accepted')
    sources = [Path(__file__).resolve(), Path(io.__file__).resolve()]
    result = {'passed': True, 'simulation_dispatched': False,
        'same_numerical_bytecode_and_globals': True, 'tested_valid_step_budgets': 4,
        'invalid_step_budgets_rejected': rejects, 'full_record_roundtrip_identical': True,
        'deterministic_gzip': True, 'overwrite_rejected_without_modification': True,
        'wrong_design_rejected': True, 'corrupt_compressed_data_rejected': True,
        'compression_ratio': seal['uncompressed_bytes']/seal['compressed_bytes'],
        'runtime_budget_adapter_not_yet_dynamically_qualified': True,
        'inputs': {str(p): api.sha(p) for p in [source, source.with_suffix('.seal.json')]},
        'sources': {str(p): api.sha(p) for p in sources},
        'artifacts': {str(p): api.sha(p) for p in OUT.iterdir() if p.is_file()}}
    api.write(OUT / 'results.json', result, raw=True)
    api.write(OUT / 'completion.json', {'passed': True, 'results_sha256': api.sha(OUT / 'results.json')})
    print('PASS budget/default and lossless storage unit checks; compression ratio', result['compression_ratio'])


if __name__ == '__main__':
    run()
