"""Bounded 0.05-s extension beyond archived cutoff, from original IID start."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage104_staging')]
import trajectory_failure_only_rescue_v1 as candidate
h=candidate.h
OUT=ROOT/'stage105_runs/original_start_extension_01'
BASE=ROOT/'stage104_evaluations/transfer_01'
START=ROOT/'stage95_designs/common_admissible_population_01/starts_s2.json'
def main():
    prior=json.loads((BASE/'results.json').read_text());p=json.loads((BASE/'protocol.json').read_text())
    if not all(prior['checks'][k] for k in ('completed','health','surface','velocity')):raise RuntimeError('nonregression prerequisite failed')
    for bindings in (prior['artifact_hashes'],p['input_hashes'],p['source_hashes']):
        for path,digest in bindings.items():
            if h.sha(path)!=digest:raise RuntimeError('lineage drift: '+path)
    cfg=json.loads(h.DESIGN.read_text());start=json.loads(START.read_text())[0]
    old=json.loads((BASE/'candidate.json').read_text());target=old['time_s']+.05
    OUT.mkdir(parents=True,exist_ok=False)
    sources={str(Path(m.__file__).resolve()):h.sha(m.__file__) for m in list(sys.modules.values())
      if getattr(m,'__file__',None) and Path(m.__file__).suffix=='.py' and ROOT in Path(m.__file__).resolve().parents}
    protocol=dict(target_s=target,extension_s=.05,wall_budget_s=360.,original_start=True,
      input_hashes={str(path):h.sha(path) for path in (START,h.DESIGN,BASE/'results.json',BASE/'candidate.json')},
      source_hashes=sources,scope='One IID fibre, whole-body downstream export only. No population fraction or permanent retention claim.')
    h.dump(OUT/'protocol.json',protocol)
    initial=dict(position_m=start['position_m'],orientation=start['orientation'],velocity_generalized=start['initial_velocity_generalized'])
    r=h.run_local(candidate,cfg,initial,2,target,360.)
    h.dump(OUT/'candidate.json',r)
    health=bool(r['minimum_gap_m'] is not None and r['minimum_gap_m']>=-5e-10 and r['max_contact_residual']<=1e-8 and r['max_force_residual']<=1e-8 and r['max_momentum_residual']<=1e-8 and r['max_reynolds']<=3)
    completed=bool(r['status']=='present_at_horizon' and abs(r['time_s']-target)<1e-12)
    exited=bool(r['status']=='full_window_exit' and 0<r['time_s']<=target)
    result=dict(status=r['status'],target_s=target,time_s=r['time_s'],runtime_s=r['runtime_seconds'],
      numerical_health_passed=health,requested_observation_resolved=health and (completed or exited),
      whole_body_exit=exited,rescue_counts=r['nullspace_rescue'],extended_beyond_old_cutoff=bool(r['time_s']>old['time_s']),
      artifact_hashes={str(path):h.sha(path) for path in OUT.glob('*.json')})
    h.dump(OUT/'results.json',result);h.dump(OUT/'completion.json',dict(status='complete_resolved' if result['requested_observation_resolved'] else 'complete_unresolved',results_sha256=h.sha(OUT/'results.json')))
    print(json.dumps(result,default=h.json_value),flush=True)
if __name__=='__main__':main()
