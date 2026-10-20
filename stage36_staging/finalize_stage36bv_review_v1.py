"""Numerical signal audit, immutable physical review and next-stage contract."""
import json,hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import open_grains_ellipsoid_v1 as flow
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36bv_review_and_next_20260911/review_01';O.mkdir(parents=True,exist_ok=False)
C=R/'stage36_evaluations/stage36bu_equal_volume_comparison_20260911/run_01/results.json'
A=R/'stage36_evaluations/stage36bt_scientific_review_20260911/audit_02/results.json'
L=R/'stage36_evaluations/stage36bt_scientific_review_20260911/literature_screen.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads(C.read_text());assert c['passed']
cfg={'signal_to_observed_resolution_difference_min':5,'additional_prolate_n':256,'scope':'local mobility at three positions only'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2))
rows=[]
for v in c['rows']:
 z,h=flow.solve([v['x'],0,0],np.eye(3),256)
 fine=v['prolate_speed'];sphere=v['sphere'][-1]['motion'][0]
 observed_error=abs(fine-z[0])+abs(sphere-v['sphere'][0]['motion'][0])
 signal=abs(fine-sphere);ratio=signal/max(observed_error,1e-16)
 row={'x':v['x'],'prolate_speed':fine,'sphere_speed':sphere,'prolate_minus_sphere_percent':100*(fine/sphere-1),
 'prolate_256':z.tolist(),'health_256':h,'signal_to_observed_resolution_difference':float(ratio)}
 rows.append(row);print(json.dumps(row),flush=True)
# Audit the recorded input hash graph, with a visited set to avoid duplicate work.
seen=set();bad=[];checked=[]
def visit(path):
 path=Path(path)
 if str(path) in seen:return
 seen.add(str(path));d=json.loads(path.read_text())
 for name,expected in d.get('input_hashes',{}).items():
  p=Path(name);ok=p.exists() and sha(p)==expected;checked.append({'path':name,'match':ok})
  if not ok:bad.append(name)
  elif p.suffix=='.json' and p.name=='results.json':visit(p)
visit(C);visit(A)
passed=not bad and all(v['signal_to_observed_resolution_difference']>=5 for v in rows)
res={'passed':passed,'rows':rows,'hash_checks':checked,'hash_mismatches':bad,
 'external_validation':'not established: current observable and physical system do not match screened data',
 'input_hashes':{str(p):sha(p) for p in [Path(__file__),C,A,L,O/'contract.json']},
 'uncertainty_note':'resolution differences are empirical indicators, not rigorous total error bounds'}
(O/'results.json').write_text(json.dumps(res,indent=2))
fig,ax=plt.subplots(figsize=(6.8,4.2),layout='constrained')
ax.plot([v['x'] for v in rows],[v['prolate_minus_sphere_percent'] for v in rows],'o-',color='#176b87')
ax.axhline(0,color='gray',lw=1);ax.grid(alpha=.2)
ax.set(xlabel='Position x / grain radius',ylabel='Prolate speed relative to sphere (%)',title='Equal-volume shape effect: local axial mobility')
fig.savefig(O/'shape_mobility.png',dpi=180);plt.close(fig)
nextcfg={'status':'prepared, not executed','question':'how do orientation and lateral starting position affect finite-body passage?',
 'shapes':{'sphere_radius':float(np.cbrt(.002)),'prolate_axes':[.2,.1,.1]},
 'starting_centre_x':-4.2,'outlet_plane_x':4.,'lateral_y':[0,.15,-.15],'prolate_angles_degrees':[0,45,90],
 'sphere_cases':3,'prolate_cases':9,'time_horizon_star':100,
 'physics':'fixed grains; rigid particle; steady Stokes hydrodynamics; no attachment model',
 'count_release':'entire body support lies downstream of outlet',
 'mass_release':'volume fraction downstream, density constant within each body',
 'categories':['fully released','still present at horizon','outside qualified clearance domain','numerical failure'],
 'censoring':'clearance stops are unresolved and never labelled physically retained',
 'release_bounds':'lower = released/N; upper = (released+unresolved)/N; finite-horizon still-present reported separately',
 'numerics':'three time steps; direct pose checks; no extrapolation; orientations remain orthonormal; force and boundary residual gates',
 'required_before_run':['implement domain-bounded terminal events','qualify local mobility for off-centre and rotated poses'],
 'external_validation':'reserve experimental conditions after matching dimensional groups, geometry and observable; do not fit current centreline result'}
(O/'next_stage_contract.json').write_text(json.dumps(nextcfg,indent=2))
lines=['# Scientific and physical review — Stage36BT–BV','',
 'Decision: the centreline passage has additional numerical support. Physical validation of soil release remains unestablished. The next local equal-volume comparison has now been executed.',
 '', '## Evidence', '',
 '- Six fresh n=384 direct solves pass the 0.1% frozen-table speed criterion (maximum 0.09644%), including a negative-x symmetry test. These are pointwise checks, not a global error bound.',
 '- Independent cross-section integration confirms the ellipsoid volume-crossing formula. Time quadrature verifies the integration of the same table; it is not an independent hydrodynamic solution.',
 '- The generalized ellipsoid solver reproduces the old prolate result. Sphere radius is (0.2*0.1*0.1)^(1/3)=0.1259921 grain radii; volume and flow geometry match.',
 '', '| x / grain radius | Prolate speed difference from sphere | Signal / observed resolution difference |','|---:|---:|---:|']
lines += [f"| {v['x']:.4f} | {v['prolate_minus_sphere_percent']:+.5f}% | {v['signal_to_observed_resolution_difference']:.1f} |" for v in rows]
lines += ['', '## Physical interpretation and corrections', '',
 'The model is exterior, steady, incompressible Stokes flow with fixed no-slip grains and a rigid force/torque-free body. It includes instantaneous hydrodynamic disturbance by the body. It is not a moving-soil DEM simulation. AR=2 is a prolate proxy; textile flexibility, curvature and large aspect ratios remain outside this test.',
 '', 'Dimensional mapping requires grain radius a_g and far-field speed U_inf: t=t* a_g/U_inf, Re_g=rho_f U_inf a_g/mu. Small Reynolds and particle-response ratios, negligible settling relative to flow, and negligible Brownian motion must be demonstrated for a proposed experiment. Force-free PET motion requires gravity to be negligible or separately accounted for.',
 '', 'The geometric gap is one grain radius; body length is 0.4 grain radii and its transverse diameter is 0.2. A centred aligned body has positive clearance and the model contains no adhesion. Complete passage is therefore a useful kinematic benchmark but a weak test of retention. One-body volume crossing is not an effluent population breakthrough curve.',
 '', 'The previous time-step code permits a terminal midpoint just beyond the table endpoint and stores an overshoot. The quadrature event time stays within the table domain and is the defensible timing reference; future trajectories must terminate without extrapolation. The previous visual-QA pass also overstated layout quality: its footer overlaps the x-axis labels. Raw artifacts are preserved.',
 '', 'Tiny force residuals mainly reflect the solved algebraic constraint, rather than an independent traction audit. Numerical boundary checks, spatial refinement and fresh direct solves provide additional evidence. More significant figures in the transit time do not imply equivalent physical accuracy.',
 '', '## External validation assessment', '',
 'The separately saved literature_screen.json contains a reported-text sphere/fragment recovery target from Ameen et al. (2024), Section 4.3, and a fibre-transport source from Cohen et al. (2025). Neither is currently a matched validation test. No calibration or validation score has been manufactured. The fibre supporting tables remain to be retrieved and checked.',
 '', '## Next stage', '',
 'A 12-case matched initial-condition design is saved in next_stage_contract.json. Off-centre/rotated mobility and bounded terminal events must be qualified before executing that population. Failed or clearance-censored paths will not be silently converted into retention. No new physical experiment is required; use independent published observations once a comparable model configuration exists.',
 '', f'Hash graph audit: {len(checked)} recorded input bindings checked; {len(bad)} mismatches. Local shape-signal check passed: {passed}.']
(O/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'passed':passed,'hash_checks':len(checked),'hash_mismatches':bad}),flush=True)
