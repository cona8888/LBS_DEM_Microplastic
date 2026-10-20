"""Create-only evidence helpers for the bounded, nonadvancing contact replay."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, time

ROOT = Path(__file__).resolve().parents[1]
BASE = 'exhausted_failure_replay_20261007'
DESIGNS = ROOT/'stage226_designs'/BASE
OUT = ROOT/'stage226_evaluations'/BASE
AUTH = DESIGNS/'authorization_01.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def commit(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.write('\n')


def utc():
    return datetime.now(timezone.utc).isoformat()


def bound():
    a=read(AUTH)
    if time.time()>=datetime.fromisoformat(a['end_utc']).timestamp():
        raise RuntimeError('Stage226 bounded contact replay cutoff')
    return a


def verify(mapping):
    for path,value in mapping.items():
        if sha(path)!=value:raise RuntimeError('Source/input changed: '+path)


def sealed(path):
    p=Path(path);row=read(p)
    if read(p.parent/'completion.json')['results_sha256']!=sha(p):
        raise RuntimeError('Unsealed evidence '+str(p))
    return row


def environment():
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
        if os.environ.get(key)!='1':raise RuntimeError('One numerical thread required: '+key)


def prepare_authorization():
    commit(AUTH,dict(stage='Stage226 bounded exhausted-failure contact replay',
        human_authorization='User next instruction after closed overnight campaign and proposed contact-reuse qualification.',
        start_utc='2026-10-07T16:00:34+00:00',end_utc='2026-10-07T16:30:34+00:00',
        created_utc=utc(),maximum_wall_seconds=1800,maximum_nonadvancing_outer_calls=784,
        maximum_new_trajectory_steps=0,maximum_saved_transport_steps=0,
        fixture_domain='All 66 recorded sample-0 fibre fallback poses and 32 deterministic healthy controls; fixed captured operands, no trajectory advancement.',
        hypothesis='A completed exhausted same-system search can be reused only in the same inner contact call, preserving all equations, original route order and physical acceptance.',
        physics_changes=[],scientific_gate_changes=[],simulation_dispatch=False,
        production_authorized=False,overnight_campaign_reopened=False,
        minimum_material_gain_fraction=0.05,logical_cpu=14,threads=1,
        maximum_nfev_per_optimizer=2000,qualification_required='Exact array bytes for accepted velocity/forces, unchanged physical health and routes apart from explicitly declared wall timings; unchanged independent signed-gap, cone, residual, force closure, dissipation and association audits; truthful independently audited exhausted-search references.',
        failure_rule='Stop dependent dispatch on any equality, physics, witness, source identity, wall budget or call-cap failure. Preserve each create-only failed attempt.',
        claim_boundary='Zero-trajectory fixed-pose implementation and local cost screen only. Transition, exact restart and complete-path/event qualification remain required before production.',
        sources={str(Path(__file__).resolve()):sha(__file__)},
        inputs={str(ROOT/'stage224_evaluations/contact_cost_screen_20261007/decision_01/results.json'):sha(ROOT/'stage224_evaluations/contact_cost_screen_20261007/decision_01/results.json'),
                str(ROOT/'stage224_evaluations/contact_cost_screen_20261007/decision_01/completion.json'):sha(ROOT/'stage224_evaluations/contact_cost_screen_20261007/decision_01/completion.json'),
                str(ROOT/'stage222_evaluations/overnight_coarser_20261007/final_disposition_01/results.json'):sha(ROOT/'stage222_evaluations/overnight_coarser_20261007/final_disposition_01/results.json')}))
    print('BOUNDED_CONTACT_REPLAY_AUTHORIZATION',sha(AUTH),'zero trajectory steps')


if __name__=='__main__':prepare_authorization()
