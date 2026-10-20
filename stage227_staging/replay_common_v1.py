"""Create-only evidence and shared limits for Stage227 fixed-pose work."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, time

ROOT=Path(__file__).resolve().parents[1]
DESIGNS=ROOT/'stage227_designs/contact_evidence_policy_20261007'
OUT=ROOT/'stage227_evaluations/contact_evidence_policy_20261007'
AUTH=DESIGNS/'authorization_01.json'
PRIOR=ROOT/'stage226_evaluations/exhausted_failure_replay_20261007'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def commit(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')


def utc():return datetime.now(timezone.utc).isoformat()


def bound():
    a=read(AUTH)
    if time.time()>=datetime.fromisoformat(a['end_utc']).timestamp():
        raise RuntimeError('Stage227 bounded fixed-pose cutoff')
    return a


def verify(mapping):
    for p,wanted in mapping.items():
        if sha(p)!=wanted:raise RuntimeError('Source/input changed: '+p)


def sealed(path):
    path=Path(path);r=read(path)
    if read(path.parent/'completion.json')['results_sha256']!=sha(path):
        raise RuntimeError('Unsealed result: '+str(path))
    return r


def environment():
    for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
        if os.environ.get(k)!='1':raise RuntimeError('One numerical thread required: '+k)


def used_outer_calls():
    total=0
    for launch in OUT.glob('*/launch.json'):
        folder=launch.parent
        result=folder/'results.json'; failure=folder/'failure.json'
        if result.is_file():
            r=sealed(result);total+=r['outer_calls_attempted']
        elif failure.is_file():total+=read(failure)['outer_calls_attempted']
        else:raise RuntimeError('Unfinished Stage227 launch reservation: '+str(folder))
    return total


def prepare_authorization():
    proposal=DESIGNS/'proposal_01.json';p=read(proposal);verify(p['sources']);verify(p['inputs'])
    r=sealed(PRIOR/'final_disposition_01/results.json');assert r['shared_outer_calls_attempted']==603
    inputs=[proposal,PRIOR/'final_disposition_01/results.json',PRIOR/'final_disposition_01/completion.json',
        PRIOR/'fixtures_01/fixtures.json',PRIOR/'fixtures_01/results.json',PRIOR/'fixtures_01/completion.json']
    commit(AUTH,dict(stage='Stage227 bounded narrow route-evidence reuse qualification',utc=utc(),
        human_authorization='User next instruction after completed Stage226 and proposed tiny narrow-evidence gate.',
        start_utc='2026-10-07T17:33:34+00:00',end_utc='2026-10-07T18:03:34+00:00',maximum_wall_seconds=1800,
        maximum_nonadvancing_outer_calls=640,maximum_new_trajectory_steps=0,maximum_saved_transport_steps=0,
        logical_cpu=14,threads=1,qualified_python='Python3.12.9',minimum_material_gain_fraction=0.05,
        tiny_fixture_ids=['recorded_fallback_trial_00040','healthy_early_success_trial_00000'],
        first_gate='Four outercalls: original+candidate on one fallback and one healthy fixture; require actual append-qualified reuse on fallback, none on healthy, exact paired all scientific outputs/route rows, independent original physics/association audits, and actual-hit adversarial controls.',
        conditional_broader_gate='Only after sealed tiny+mutation passes, freeze separate98fixture design with196qualification and392timingcalls within same cap/deadline; complete candidate costs included, no representative campaign inference.',
        hypothesis='An exactly associated failed early-route record may be appended between exact same-inner helper requests while every original record and all numeric seed certificates remain intact.',
        evidence_policy_revision='Prospective Stage227 independent append-proof contract; Stage226 exact-certificate rule and all failed attempts remain unchanged.',
        physics_changes=[],physical_gate_changes=[],route_order_changes=[],simulation_dispatch=False,production_authorized=False,
        maximum_nfev_per_optimizer=2000,
        failure_rule='Stop dependent dispatch on source, equality, physics, witness, append association, numerical certificate, call-budget or deadline failure; retain each create-only version. Any repair uses a new source/design/output version and shared remaining budget.',
        claim_boundary='Nonadvancing local implementation/cost qualification only; transfer, transition, exactrestart and complete-path/event gates remain required before production. Overnight remainsclosed and heartbeatpaused.',
        sources={str(Path(__file__).resolve()):sha(__file__)},inputs={str(x):sha(x) for x in inputs}))
    print('STAGE227_AUTHORIZED',sha(AUTH),'end18:03:34UTC','max640calls','zero trajectories')


if __name__=='__main__':prepare_authorization()
