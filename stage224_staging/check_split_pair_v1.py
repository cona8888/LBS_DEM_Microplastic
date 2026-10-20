"""Bounded pointwise screening only; never integrates or installs a solver.

Authenticates a saved Stage222 transaction, freezes a deterministic fixture
inventory, then compares split getters with the live stack's strict compiled
analytic pair. A pass is arithmetic screening, not optimizer/physics/speedup
qualification. No source imported here is edited or installed in another process.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, lzma, os, sys, time, traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage196_staging'), str(ROOT/'stage194_staging')]
import numpy as np
import split_analytic_pair_v1 as candidate

BASE = 'contact_cost_screen_20261007'
DESIGN = ROOT/'stage224_designs'/BASE/'pointwise_01.json'
OUT = ROOT/'stage224_evaluations'/BASE/'pointwise_01'
FOLDER = ROOT/'stage222_runs/overnight_coarser_20261007/run_01/s2_i0_fibre_f0p125/segment_00247'
DEADLINE = datetime.fromisoformat('2026-10-07T12:10:57+00:00').timestamp()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def commit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def authenticate():
    row = read(FOLDER/'results.json')
    assert read(FOLDER/'completion.json')['results_sha256'] == sha(FOLDER/'results.json')
    assert row['passed'] and row['transaction_profiled']
    for path, digest in row['artifacts'].items():
        assert sha(path) == digest, path
    seal = read(FOLDER/'call.json.seal.json')
    compressed = (FOLDER/'call.json.xz').read_bytes()
    assert hashlib.sha256(compressed).hexdigest() == seal['compressed_sha256']
    raw = lzma.decompress(compressed)
    assert len(raw) == seal['uncompressed_bytes']
    assert hashlib.sha256(raw).hexdigest() == seal['uncompressed_sha256']
    wrapper = json.loads(raw)
    assert wrapper['design_sha256'] == row['design_sha256'] == seal['design_sha256']
    # Only captured inputs are read. No history is reconstructed or advanced.
    return wrapper['packed_envelope']['payload']


def fixtures(payload):
    fields = ('vfree','mobility','jacobian','gaps_m','dt_s','friction')
    rows = []
    for name, count in (('early_attempts',32),('fallback_systems',16)):
        data = payload[name]
        # Failed early attempts are sometimes telemetry-only: their exact
        # inputs occur in the separate fallback capture. Do not reconstruct
        # missing operands or silently label those rows as pointwise fixtures.
        available = [i for i,r in enumerate(data) if all(k in r for k in fields)]
        assert len(available) >= count
        for j in np.linspace(0,len(available)-1,count,dtype=int):
            index = available[int(j)]
            row = data[int(index)]
            rows.append(dict(label=f'{name}_{index}', **{k:row[k] for k in fields}))
    # Explicit degenerate normal and tangential branches, with positive scales.
    J = np.array([[1,0,0,0,0,0],[0,1,0,0,0,0],[0,0,1,0,0,0],
                  [0,0,0,1,0,0],[0,0,0,0,1,0],[0,0,0,0,0,1],
                  [1,0,0,1,0,0],[0,1,0,0,1,0],[0,0,1,0,0,1]],float)
    rows.append(dict(label='zero_speed_zero_gap',vfree=[0.]*6,mobility=np.eye(6).tolist(),
                     jacobian=J.tolist(),gaps_m=[0.]*3,dt_s=1.,friction=.3))
    return rows


def prepare():
    assert time.time() < DEADLINE
    rows = fixtures(authenticate())
    commit(OUT/'fixtures.json', rows)
    source_paths = [Path(__file__).resolve(), Path(candidate.__file__), Path(candidate.previous.__file__)]
    input_paths = [OUT/'fixtures.json',FOLDER/'results.json',FOLDER/'completion.json',
                   FOLDER/'call.json.xz',FOLDER/'call.json.seal.json']
    design = dict(stage='Stage224 split analytic pair arithmetic screen',new_trajectory_steps=0,
                  fixture_count=len(rows),points_per_fixture=8,maximum_wall_seconds=45,
                  deadline_utc='2026-10-07T12:10:57+00:00',rng_seed=224,
                  sources={str(p):sha(p) for p in source_paths},inputs={str(p):sha(p) for p in input_paths},
                  criteria='Exact array bytes; separate getter laziness; retained-output and memo mutation isolation; unchanged input arrays.',
                  production_authorized=False,optimizer_qualified=False,
                  simulation_dispatch=False,timing_claim=False)
    commit(DESIGN,design)
    print('PREPARED',len(rows),'zero trajectory steps')


def run():
    design = read(DESIGN)
    assert time.time() < DEADLINE
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
        assert os.environ.get(key) == '1'
    for path,digest in {**design['sources'],**design['inputs']}.items():
        assert sha(path) == digest, path
    OUT.mkdir(parents=True,exist_ok=True)
    commit(OUT/'launch.json',dict(pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat(),
                               argv=sys.argv,design_sha256=sha(DESIGN),new_trajectory_steps=0))
    start = time.monotonic()
    rng = np.random.default_rng(design['rng_seed'])
    checked = []
    try:
        for fixture in read(OUT/'fixtures.json'):
            assert time.time() < DEADLINE
            assert time.monotonic()-start < design['maximum_wall_seconds']
            args = tuple(np.array(fixture[k],dtype=float) for k in ('vfree','mobility','jacobian','gaps_m')) + (fixture['dt_s'],fixture['friction'])
            snapshots = [a.tobytes() for a in args[:4]]
            baseline,*constants = candidate.previous.optimized_system(*args)
            split,*other_constants = candidate.optimized_system(*args)
            assert all(np.asarray(a).tobytes()==np.asarray(b).tobytes() for a,b in zip(constants,other_constants))
            points = [np.zeros(9),np.full(9,-0.),np.ones(9),-np.ones(9),
                      rng.normal(size=9),rng.normal(size=9)*1e4,
                      np.r_[1.,0.,0.,1.,0.,0.,1.,0.,0.],
                      np.r_[1.,.3,0.,1.,0.,.3,1.,.3,0.]]
            previous_result = None
            for y in points:
                expected = baseline(y)
                old_jac = split.counters['jacobian_computations']
                f = split.residual(y)
                assert split.counters['jacobian_computations'] == old_jac
                assert f.tobytes() == expected[0].tobytes()
                old_f = split.counters['residual_computations']
                J = split.derivative(y)
                assert split.counters['residual_computations'] == old_f
                assert J.tobytes() == expected[1].tobytes()
                if previous_result is not None:
                    assert all(a.tobytes()==b for a,b in previous_result)
                previous_result = [(f,f.tobytes()),(J,J.tobytes())]
                f.flat[0]=999.;J.flat[0]=999.
                # Mutation of returned arrays cannot contaminate memoized data.
                assert split.residual(y).tobytes()==expected[0].tobytes()
                assert split.derivative(y).tobytes()==expected[1].tobytes()
                assert all(a.tobytes()==b.tobytes() for a,b in zip(split(y),expected))
                previous_result = None
            # Retain returned values across a distinct input, then check ownership.
            retained = split(points[0]);saved = tuple(a.tobytes() for a in retained)
            split(points[1])
            assert tuple(a.tobytes() for a in retained)==saved
            assert snapshots == [a.tobytes() for a in args[:4]]
            checked.append(dict(label=fixture['label'],exact_points=len(points),counters=dict(split.counters)))
        for path,digest in {**design['sources'],**design['inputs']}.items():
            assert sha(path)==digest,path
        result = dict(passed=True,utc=datetime.now(timezone.utc).isoformat(),design_sha256=sha(DESIGN),
                      new_trajectory_steps=0,fixtures=len(checked),exact_points=sum(r['exact_points'] for r in checked),
                      elapsed_seconds=time.monotonic()-start,checks=checked,
                      residual_getter_never_computed_jacobian=True,derivative_getter_never_computed_residual=True,
                      returned_array_mutation_isolated=True,production_authorized=False,
                      optimizer_qualified=False,physics_qualified=False,speedup_measured=False,
                      claim='Pointwise arithmetic screening only. Full optimizer/force-route, physical audit, restart and trajectory/event gates remain open.')
        commit(OUT/'results.json',result)
        commit(OUT/'completion.json',dict(passed=True,results_sha256=sha(OUT/'results.json')))
        print('POINTWISE_PASS',result['fixtures'],result['exact_points'],'no optimizer or trajectory qualification')
    except Exception as error:
        commit(OUT/'failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),
                                     checked=checked,new_trajectory_steps=0))
        raise


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']:prepare()
    elif sys.argv[1:] == ['run']:run()
    else:raise ValueError('prepare | run')
