"""Immutable bounded segments of one original-start 2-PV fibre observation."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage106_staging'))
import verify_checkpoint_v2 as lib
h=lib.h
OUT=ROOT/'stage108_runs/first_iid_fibre_2pv_01'
START=ROOT/'stage95_designs/common_admissible_population_01/starts_s2.json'
GATE=ROOT/'stage107_evaluations/fresh_process_01'
def sha_state(state):return hashlib.sha256(json.dumps(state,sort_keys=True,allow_nan=True).encode()).hexdigest()
def main():
    # Explicit segment number, never auto-resume or overwrite evidence.
    number=int(sys.argv[1]) if len(sys.argv)>1 else 1
    if number<1:raise ValueError('positive segment number required')
    manifest_path=OUT/'manifest.json'
    if number==1:
        gate=json.loads((GATE/'results.json').read_text())
        if not gate['passed']:raise RuntimeError('restart gate failed')
        for p,d in gate['artifact_hashes'].items():
            if h.sha(p)!=d:raise RuntimeError('gate artifact drift')
        cfg=json.loads(h.DESIGN.read_text());_,_,L,_,files=h.matrix_case_v1.load(2)
        sources={str(Path(m.__file__).resolve()):h.sha(m.__file__) for m in list(sys.modules.values())
          if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
        inputs={str(p):h.sha(p) for p in (START,h.DESIGN,GATE/'results.json',*files)}
        binding=hashlib.sha256(json.dumps([sources,inputs],sort_keys=True).encode()).hexdigest()
        OUT.mkdir(parents=True,exist_ok=False)
        h.dump(manifest_path,dict(source_hashes=sources,input_hashes=inputs,binding=binding,horizon_s=2*L/cfg['target_mean_interstitial_velocity_m_s'],horizon_pv=2.,wall_budget_s=300.,seed=2,sample_id=0,
          scope='Single original-start fibre, fixed matrix/flow, whole-body downstream export; no population release estimate.'))
    manifest=json.loads(manifest_path.read_text())
    for section in ('source_hashes','input_hashes'):
        for path,digest in manifest[section].items():
            if h.sha(path)!=digest:raise RuntimeError('immutable binding drift: '+path)
    lib.Runner.binding=manifest['binding'];lib.Runner.checkpoint=None;lib.Runner.pause=None
    previous_hash=None;start_time=0.
    if number>1:
        prior=OUT/f'segment_{number-1:04d}'
        completion=json.loads((prior/'completion.json').read_text())
        if h.sha(prior/'result.json')!=completion['result_sha256']:raise RuntimeError('prior result drift')
        previous=json.loads((prior/'result.json').read_text())
        if previous['status']!='incomplete_budget':raise RuntimeError('prior segment is not resumable')
        lib.Runner.checkpoint=previous['checkpoint'];start_time=previous['time_s']
        if sha_state(lib.Runner.checkpoint['state'])!=lib.Runner.checkpoint['state_sha256']:raise RuntimeError('checkpoint digest drift')
        previous_hash=h.sha(prior/'result.json')
    segment=OUT/f'segment_{number:04d}';segment.mkdir(exist_ok=False)
    h.dump(segment/'launch.json',dict(manifest_sha256=h.sha(manifest_path),prior_result_sha256=previous_hash,start_time_s=start_time))
    cfg=json.loads(h.DESIGN.read_text());start=json.loads(START.read_text())[0]
    state=dict(position_m=start['position_m'],orientation=start['orientation'],velocity_generalized=start['initial_velocity_generalized'])
    r=h.run_local(lib.Runner,cfg,state,2,manifest['horizon_s'],manifest['wall_budget_s'])
    h.dump(segment/'result.json',r)
    cp=r.get('checkpoint')
    resumable=bool(r['status']=='incomplete_budget' and cp is not None and sha_state(cp['state'])==cp['state_sha256'])
    health=bool(r['minimum_gap_m'] is not None and r['minimum_gap_m']>=-5e-10 and r['max_contact_residual']<=1e-8 and r['max_force_residual']<=1e-8 and r['max_momentum_residual']<=1e-8 and r['max_reynolds']<=3)
    record=dict(status=r['status'],time_s=r['time_s'],observed_pv=2*r['time_s']/manifest['horizon_s'],runtime_s=r['runtime_seconds'],
      checkpoint_verified=resumable,numerical_health_passed=health,start_time_s=start_time,
      result_sha256=h.sha(segment/'result.json'),manifest_sha256=h.sha(manifest_path))
    h.dump(segment/'completion.json',record);print(json.dumps(record,default=h.json_value),flush=True)
if __name__=='__main__':main()
