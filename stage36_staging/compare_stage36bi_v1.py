"""Predeclared fine/coarse coupled-response comparison."""
import json,hashlib
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]/'stage36_evaluations'
out=root/'stage36bi_coupling_refinement_20260911/comparison_01';out.mkdir(exist_ok=False)
cfg={'relative_limit':.001,'load':[1e-4,0,0,0,0,0],'comparisons':['resistance','mobility','translation_rotation_block','lateral_velocity','angular_velocity'],'scope':'single tilted off-centre pose'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
operators=[];hashes={}
for stage in ['stage36bh_offset_tilt_20260911','stage36bi_coupling_refinement_20260911']:
    p=root/stage/'verification_01';r=json.loads((p/'results.json').read_text());op=p/'operator.npz'
    h=hashlib.sha256(op.read_bytes()).hexdigest()
    if not r['passed'] or h!=r['operator_hash']:raise ValueError('invalid provenance')
    hashes[str(op)]=h
    with np.load(op,allow_pickle=False) as d:operators.append((d['resistance'].copy(),d['mobility'].copy()))
(Rc,Mc),(Rf,Mf)=operators
relative=lambda a,b:float(np.linalg.norm(a-b)/np.linalg.norm(b))
zc=Mc@cfg['load'];zf=Mf@cfg['load']
errors={'resistance':relative(Rc,Rf),'mobility':relative(Mc,Mf),'translation_rotation_block':relative(Rc[:3,3:],Rf[:3,3:]),'lateral_velocity':abs(float((zc[1]-zf[1])/zf[1])),'angular_velocity':abs(float((zc[5]-zf[5])/zf[5]))}
result={'errors':errors,'passed':all(v<.001 for v in errors.values()),'fine_velocity':zf[:3].tolist(),'fine_omega':(zf[3:]/2).tolist(),'same_signs':bool(zc[1]*zf[1]>0 and zc[5]*zf[5]>0),'hashes':hashes}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
