"""Finalize completed pose cases after a path-type error in summary hashing."""
import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];base=R/'stage36_evaluations/stage36bw_pose_qualification_20260911'
O=base/'run_03';O.mkdir(exist_ok=False);P=base/'run_02'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cfg=json.loads((P/'contract.json').read_text())
paths=[P/f'case_{i:02}.json' for i in range(1,13)];rows=[json.loads(p.read_text()) for p in paths]
prior_matches=sha(base/'run_01/results.json')==cfg['prior_sha256']
res={'passed':all(r['passed'] for r in rows) and prior_matches,'rows':rows,'prior_hash_matches':prior_matches,
 'input_hashes':{str(p):sha(p) for p in paths+[Path(__file__),P/'contract.json']},
 'recovery':'All twelve case files completed. Final summary failed because a string path was passed to a Path-only hash helper. No physical solves rerun.',
 'hash_scope':'case files hashed at recovery; prior result checked against pre-run contract hash',
 'trajectories_executed':False}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps({'passed':res['passed'],'cases':len(rows)}))
