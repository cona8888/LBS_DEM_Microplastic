"""Create-only evidence and shared limits for Stage228 nonadvancing work."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, time
ROOT=Path(__file__).resolve().parents[1]
DESIGNS=ROOT/'stage228_designs/verification_overhead_20261007'
OUT=ROOT/'stage228_evaluations/verification_overhead_20261007'
AUTH=DESIGNS/'authorization_01.json'
PRIOR=ROOT/'stage226_evaluations/exhausted_failure_replay_20261007'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def commit(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def utc():return datetime.now(timezone.utc).isoformat()
def bound():
    a=read(AUTH)
    if time.time()>=datetime.fromisoformat(a['end_utc']).timestamp():raise RuntimeError('Stage228 bounded fixed-pose cutoff')
    return a
def verify(mapping):
    for p,h in mapping.items():
        if sha(p)!=h:raise RuntimeError('Source/input changed: '+p)
def sealed(path):
    path=Path(path);r=read(path)
    if read(path.parent/'completion.json')['results_sha256']!=sha(path):raise RuntimeError('Unsealed result: '+str(path))
    return r
def environment():
    for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
        if os.environ.get(k)!='1':raise RuntimeError('One numerical thread required: '+k)
def used_outer_calls():
    total=0
    for launch in OUT.glob('*/launch.json'):
        folder=launch.parent
        if (folder/'results.json').is_file():total+=sealed(folder/'results.json')['outer_calls_attempted']
        elif (folder/'failure.json').is_file():total+=read(folder/'failure.json')['outer_calls_attempted']
        else:raise RuntimeError('Unfinished Stage228 launch reservation: '+str(folder))
    return total
def prepare_authorization():
    proposal=DESIGNS/'proposal_01.json';p=read(proposal);verify(p['sources']);verify(p['inputs'])
    prior=ROOT/'stage227_evaluations/contact_evidence_policy_20261007/final_disposition_01/results.json'
    assert sealed(prior)['shared_outer_calls_attempted']==592
    inputs=[proposal,prior,prior.parent/'completion.json',PRIOR/'fixtures_01/fixtures.json',PRIOR/'fixtures_01/results.json',PRIOR/'fixtures_01/completion.json']
    commit(AUTH,dict(stage='Stage228 bounded verification-overhead qualification',utc=utc(),
        human_authorization='User next after closed Stage227 and proposed Stage228 verification-overhead gate.',
        start_utc='2026-10-07T19:03:18+00:00',end_utc='2026-10-07T19:33:18+00:00',maximum_wall_seconds=1800,
        maximum_nonadvancing_outer_calls=640,maximum_new_trajectory_steps=0,maximum_saved_transport_steps=0,
        logical_cpu=14,threads=1,qualified_python='Python3.12.9',minimum_material_gain_fraction=0.05,
        tiny_fixture_ids=['recorded_fallback_trial_00040','healthy_early_success_trial_00000'],
        first_gate='Four diagnostically profiled paired original/unchanged-candidate outercalls; attribution only, exact outputs and original physical audits.',
        conditional_tiny_gate='Profile-informed separately versioned equation-preserving optimization; actual fallback hit, zero healthy hits, exact scientific outputs, independent original physical and witness gates, all32 evidence corruption controls and fresh real-binding/code/mutable/operand/cutoff controls.',
        conditional_broader_gate='Only after sealed tiny+mutation passes, separately freeze98fixture196qualification+392timingcalls, full candidate costs included, explicit both strata; shared cap/deadline.',
        physics_changes=[],physical_gate_changes=[],route_order_changes=[],simulation_dispatch=False,production_authorized=False,
        maximum_nfev_per_optimizer=2000,
        failure_rule='Stop dependent dispatch on equality/physical/evidence/guard/budget failure. Preserve each create-only version; equation-preserving repairs require separate source/design/output within shared remaining budget.',
        claim_boundary='Local nonadvancing verification/cost gate only. No production, dynamic transfer, exactrestart, fullpath/event or shape/flow inference. Closed overnight remainsclosed and heartbeatpaused.',
        sources={str(Path(__file__).resolve()):sha(__file__)},inputs={str(x):sha(x) for x in inputs}))
    print('STAGE228_AUTHORIZED',sha(AUTH),flush=True)
if __name__=='__main__':prepare_authorization()
