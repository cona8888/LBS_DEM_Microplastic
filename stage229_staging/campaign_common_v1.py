"""Create-only Stage229 authorizations, evidence and shared overnight limits."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, time
ROOT=Path(__file__).resolve().parents[1]
DESIGNS=ROOT/'stage229_designs/overnight_20261007'
OUT=ROOT/'stage229_evaluations/overnight_20261007'
RUN=ROOT/'stage229_runs/overnight_20261007'
AUTH=DESIGNS/'authorization_01.json'
PRIOR=ROOT/'stage226_evaluations/exhausted_failure_replay_20261007'
START='2026-10-07T19:58:49+00:00'
END='2026-10-08T07:58:49+00:00'
CUTOFF='2026-10-08T07:48:49+00:00'
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
    if not datetime.fromisoformat(a['start_utc']).timestamp()<=time.time()<datetime.fromisoformat(a['end_utc']).timestamp():
        raise RuntimeError('Stage229 bounded overnight cutoff')
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
        else:raise RuntimeError('Unfinished Stage229 cost launch reservation: '+str(folder))
    return total
def baseline_dispatch_allowed():
    bound();r=sealed(OUT/'dispatch_decision_01/results.json');verify(r['inputs'])
    if r['baseline_allowed'] is not True or r['candidate_production_authorized'] is not False:
        raise RuntimeError('Original baseline dispatch is not qualified')
    return r
def prepare_authorization():
    old=ROOT/'stage228_evaluations/verification_overhead_20261007'
    final=sealed(old/'final_authentication_02/results.json');verify(final['artifacts'])
    assert final['shared_outer_calls_attempted']==10 and final['all_exact_launch_identities_retired']
    refs=[old/'final_authentication_02/results.json',old/'final_authentication_02/completion.json',
        old/'tiny_replay_02/results.json',old/'tiny_replay_02/completion.json',old/'metadata_controls_03/results.json',old/'metadata_controls_03/completion.json',
        ROOT/'stage222_evaluations/overnight_coarser_20261007/final_disposition_01/results.json',
        ROOT/'stage222_evaluations/overnight_coarser_20261007/final_disposition_01/completion.json',
        ROOT/'stage220_evaluations/checkpoint_recovery_20261006/combined_evaluation_01/results.json',
        ROOT/'stage220_evaluations/checkpoint_recovery_20261006/combined_evaluation_01/completion.json',
        PRIOR/'fixtures_01/fixtures.json',PRIOR/'fixtures_01/results.json',PRIOR/'fixtures_01/completion.json']
    for p in refs:
        if p.name=='results.json':assert sealed(p).get('passed',True)
    commit(AUTH,dict(stage='Stage229 bounded overnight numerical verification',utc=utc(),
        human_authorization='User next and run code for12hours while sleeping after closed Stage228; new bounded attempt, preserve earlier closed windows.',
        start_utc=START,end_utc=END,simulation_cutoff_utc=CUTOFF,maximum_wall_seconds=43200,
        maximum_nonadvancing_outer_calls=640,maximum_new_trajectory_steps=10000000,maximum_saved_transport_steps=10000000,
        maximum_saved_steps_including_diagnostics=10000000,logical_cpu=14,threads=1,workers=1,maximum_unverified_records=1,
        minimum_material_gain_fraction=0.05,minimum_free_disk_bytes=20*1024**3,
        tiny_fixture_ids=['recorded_fallback_trial_00040','healthy_early_success_trial_00000'],
        cost_screen=dict(maximum_nonadvancing_outer_calls=640,maximum_new_trajectory_steps=0,maximum_saved_transport_steps=0,
            production_authorized=False,simulation_dispatch=False,fresh_tiny_calls=4,conditional_full_calls=588,
            gates='Fresh tiny actual hit/healthy nohit, exact paired full scientific outputs and original independent physical audits,32 corruption/22 live controls; all98poses with196qualification and392alternating warmed unprofiled timings. Report outer and complete scoped transactions by stratum; retain original5percent material gate and do not promote a favorable oversampled aggregate.'),
        independent_baseline=dict(authorized=True,requires_separately_frozen_transport_design=True,
            solver='Original unchanged Stage222/Stage219 qualified stack; optimization prototype never installed.',
            factor=0.125,automatic_factor_escalation=False,case_order=['s2_i0_fibre_f0p125','s2_i0_sphere_f0p125','s2_i124_fibre_f0p125','s2_i124_sphere_f0p125'],
            first_case='Resume authenticated569segment Stage222 seed; discard late-seed256vs128+128 qualification trajectories and restart production from original seed.',
            maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,maximum_steps_per_segment=10000,
            diagnostic_steps_per_case=512,requires_each_segment_independent_physics=True,
            requires_complete_path_gate_before_successor_case=True,comparison='Combine full inherited prefix and new tail against original fine0.03125sample0 reference; sample124 against separate selected0.0625 reference. Original thresholds unchanged.',
            performance_only_optimization_failure_does_not_block_independent_baseline=True),
        physics_changes=[],physical_gate_changes=[],route_order_changes=[],production_authorized=False,candidate_production_authorized=False,simulation_dispatch=True,
        maximum_nfev_per_optimizer=2000,
        failure_rule='Any cost scientific/physical/evidence failure blocks baseline dispatch; performance-only failure retains negative optimization evidence and permits separately authorized original baseline. Any transport physical/fullpath/source/restart/ledger failure stops dependent case dispatch. Preserve raw/unresolved attempts. Version any equation-preserving repair within remaining shared absolute window and caps; never mutate frozen active bindings or increase caps.',
        claim_boundary='Numerical verification and affordability only for labelled placements at one packing/flow. No population shape/flow trend, spatial convergence or experimental validation. Twelvehours is a maximum work window, not a completion promise.',
        prior_overnight_remains_closed=True,master_plan_sha256_at_authorization=sha(ROOT/'MASTER_PLAN.md'),
        sources={str(Path(__file__).resolve()):sha(__file__)},inputs={str(p):sha(p) for p in refs}))
    print('STAGE229_AUTHORIZED',sha(AUTH),END,flush=True)
if __name__=='__main__':prepare_authorization()
