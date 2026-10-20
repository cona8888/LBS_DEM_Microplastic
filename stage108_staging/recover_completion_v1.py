"""Finalize durable first segment after post-save array serialization error."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage89_staging'))
import verify_short_seed_local_v1 as h
D=ROOT/'stage108_runs/first_iid_fibre_2pv_01'
def main():
    m=json.loads((D/'manifest.json').read_text());s=D/'segment_0001'
    if (s/'completion.json').exists():raise RuntimeError('completion exists')
    for sec in ('source_hashes','input_hashes'):
        for p,d in m[sec].items():
            if h.sha(p)!=d:raise RuntimeError('binding drift')
    r=json.loads((s/'result.json').read_text());cp=r['checkpoint']
    digest=hashlib.sha256(json.dumps(cp['state'],sort_keys=True,allow_nan=True).encode()).hexdigest()
    if digest!=cp['state_sha256'] or r['status']!='incomplete_budget':raise RuntimeError('checkpoint invalid')
    health=bool(r['minimum_gap_m'] is not None and r['minimum_gap_m']>=-5e-10 and r['max_contact_residual']<=1e-8 and r['max_force_residual']<=1e-8 and r['max_momentum_residual']<=1e-8 and r['max_reynolds']<=3)
    record=dict(status=r['status'],time_s=r['time_s'],observed_pv=2*r['time_s']/m['horizon_s'],runtime_s=r['runtime_seconds'],
      checkpoint_verified=True,numerical_health_passed=health,start_time_s=0.,result_sha256=h.sha(s/'result.json'),manifest_sha256=h.sha(D/'manifest.json'),
      recovery_note='Result/checkpoint persisted before post-processing array serialization error. Independently verified from JSON; no rerun.',recovery_source_sha256=h.sha(__file__))
    h.dump(s/'completion.json',record);print(json.dumps(record))
if __name__=='__main__':main()
