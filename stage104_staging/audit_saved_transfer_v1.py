"""Independent audit after final stdout serialization error; no rerun."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage89_staging'),str(ROOT/'stage92_staging')]
import verify_short_seed_local_v1 as h
import verify_physical_error_budget_v1 as gates
D=ROOT/'stage104_evaluations/transfer_01';OUT=ROOT/'stage104_evaluations/saved_transfer_audit_01'
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    r=json.loads((D/'results.json').read_text());c=json.loads((D/'completion.json').read_text());p=json.loads((D/'protocol.json').read_text())
    if c['results_sha256']!=h.sha(D/'results.json'):raise RuntimeError('result hash mismatch')
    count=0
    for bindings in (r['artifact_hashes'],p['input_hashes'],p['source_hashes']):
        for path,digest in bindings.items():
            if h.sha(path)!=digest:raise RuntimeError('binding mismatch: '+path)
            count+=1
    old=json.loads((ROOT/'stage96_runs/population_prefix_01/s2_i0_prolate_ar4.json').read_text())['result']
    new=json.loads((D/'candidate.json').read_text());cfg=json.loads(h.DESIGN.read_text())
    m=gates.metrics(old,new,cfg['prolate_semiaxes_m'][0])
    checks=dict(completed=bool(new['status']=='present_at_horizon' and abs(new['time_s']-old['time_s'])<1e-12),
      health=gates.health(new),surface=m['surface_displacement_bound_m']<=5e-12,velocity=m['generalized_velocity_difference_m_s']<=1e-8,
      same_steps=new['steps']==old['steps'],same_rejections=new['rejected']==old['rejected'])
    result=dict(nonregression_passed=all(checks.values()),checks=checks,metrics=m,verified_bindings=count,
      rescue_exercised=new['nullspace_rescue']['accepted']>0,original_complete_failed_preserved=True,
      execution_note='Final stdout json.dumps failed after candidate, results and completion were persisted. Saved evidence independently verified; no simulation rerun.',
      source_sha256=h.sha(__file__),original_results_sha256=h.sha(D/'results.json'))
    h.dump(OUT/'results.json',result);print(json.dumps(result,default=h.json_value))
if __name__=='__main__':main()
