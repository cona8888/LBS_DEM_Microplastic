"""Supplement all-radius gates; preserve raw output and its contract."""
import json,hashlib
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36ax_confined_sphere_20260911/verification_01'
r=json.loads((p/'results.json').read_text());checks={}
for radius in [3.,4.]:
    rows=[v for v in r['rows'] if v['radius']==radius];a,b=rows
    checks[str(radius)]=all(b[k]<.001 for k in ['particle_boundary_error','wall_boundary_error','force_error','field_error']) and abs(b['force'][0]-a['force'][0])/abs(b['force'][0])<.001
checks['hashes']=all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in r['hashes'].items())
checks['artifacts']=all(hashlib.sha256((p/k).read_bytes()).hexdigest()==v for k,v in r['artifacts'].items())
with (p/'audit.json').open('x') as f:json.dump({'checks':checks,'passed':all(checks.values()),'note':'Both radii are frozen in test source. Original contract cavity_radius is default 4; actual cases are 3 and 4 as recorded in rows.'},f,indent=2)
print(checks)
