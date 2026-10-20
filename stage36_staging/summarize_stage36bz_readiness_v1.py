"""Assemble honest trajectory readiness and computational cost evidence."""
import json,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1]
P=R/'stage36_evaluations/stage36bw_pose_qualification_20260911/run_03/results.json'
B=R/'stage36_evaluations/stage36by_bounded_baseline_20260911/run_01/results.json'
E=R/'stage36_evaluations/stage36bx_bounded_events_20260911/test_01/results.json'
V=R/'stage36_evaluations/stage36bx_bounded_events_20260911/variable_flow_01/results.json'
O=R/'stage36_evaluations/stage36bz_readiness_20260911/report_01';O.mkdir(parents=True,exist_ok=False)
p,b,e,v=[json.loads(f.read_text()) for f in [P,B,E,V]]
rows=p['rows'];passed=sum(r['passed'] for r in rows)
seconds=float(np.median([s['seconds'] for r in rows for s in r['solves'] if s['n']==384]))
calls=sum(int(np.ceil(8.4/h))*5 for h in [.2,.1,.05])*12
hours=seconds*calls/3600
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
report={'qualified_local_poses':passed,'total_local_poses':12,'bounded_events_pass':e['passed'] and v['passed'],
 'baseline_pass':b['passed'],'new_ensemble_trajectories_completed':0,
 'baseline_event_time':b['rows'][-1]['complete_release_t'],
 'cost_estimate':{'median_n384_seconds':seconds,'example_dx':[.2,.1,.05],'uncached_provider_calls':calls,'hours':hours,
 'interpretation':'planning estimate for direct full-domain RK4, excluding extra refinement; not measured ensemble runtime'},
 'next_action':'build and verify reusable fixed-grain linear algebra or a local pose surrogate before full trajectory ensemble',
 'input_hashes':{str(f):sha(f) for f in [Path(__file__),P,B,E,V]}}
(O/'results.json').write_text(json.dumps(report,indent=2))
lines=['# Stage36BW–BZ: orientation and placement readiness','',
 f'{passed}/12 local throat poses pass the unchanged spatial, rotational, boundary and force checks after selective refinement. These are local evaluations at x=0, not completed trajectories.',
 '', '## Completed work','',
 '- Preserved the first qualification run: six poses failed the rotation-refinement criterion. The failed poses were evaluated at 512 sources and reassessed against 384 sources without relaxing tolerances.',
 '- Added a bounded planar passage integrator using x as the independent coordinate. Translation, rotation, horizon handling and nonpositive axial-velocity rejection are tested. A variable-flow manufactured solution shows decreasing error at all three refinements.',
 f"- Reproduced the aligned centreline physical benchmark with no terminal extrapolation: complete passage t*={b['rows'][-1]['complete_release_t']:.9f}. This reuses the qualified flow table and adds no independent population replicate.",
 '', '| Shape | y / grain radius | angle (deg) | qualified source pair | pass |','|---|---:|---:|---|---|']
lines += [f"| {r['shape']} | {r['y']} | {r['angle_degrees']} | {r['qualification_pair']} | {r['passed']} |" for r in rows]
lines += ['', '## Physical finding','',
 'At x=0, the centred 45-degree prolate has a lateral velocity about 0.001174 times the far-field speed. Its orientation and lateral motion must evolve together. The aligned centreline table cannot represent its path. A sphere has orientation-invariant geometry, although its spin is still checked here.',
 '', '## Runtime and next implementation','',
 f'The median 384-source solve took {seconds:.2f} s. A direct 12-case calculation at axial steps 0.2, 0.1 and 0.05 would require approximately {calls:,} uncached provider queries, or {hours:.1f} CPU wall-clock hours at this measured rate, before extra refinement. This is a planning estimate; no such ensemble was launched.',
 '', 'The next implementation should reuse the fixed-grain response and verify it against these direct solves, or construct a locally refined pose surrogate with fresh held-out tests. Boundary, velocity and angular-velocity checks must remain separate. Then execute the frozen 12-case ensemble with refinement and explicit censoring.',
 '', '## Remaining limits','',
 'A local pose pass does not qualify all intermediate poses. Positive axial velocity is required by the x-parameterized integrator; recirculating paths require another formulation. Rapid nonmonotonic tail crossing needs additional event bracketing checks. All near-clearance stops remain unresolved rather than physically retained. No soil-scale release fraction or external validation is claimed.']
(O/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8');print(json.dumps(report,indent=2))
