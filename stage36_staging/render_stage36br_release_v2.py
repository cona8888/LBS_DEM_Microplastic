"""Headless render and immutable pre-comparison handoff."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
RES=ROOT/'stage36_evaluations/stage36br_finite_body_release_20260911/release_02/results.json'
HIST=ROOT/'stage36_evaluations/stage36br_finite_body_release_20260911/release_02/release_history.npz'
TABLE=ROOT/'stage36_evaluations/stage36bq_throat_table_20260911/table_04/results.json'
RENDER_FAIL=ROOT/'stage36_renders/stage36br_finite_body_release_20260911/render_01/failure.json'
HAND_FAIL=ROOT/'stage36_evaluations/stage36bs_precomparison_handoff_20260911/handoff_01/failure.json'
OUT=ROOT/'stage36_renders/stage36br_finite_body_release_20260911/render_02'
HAND=ROOT/'stage36_evaluations/stage36bs_precomparison_handoff_20260911/handoff_02'
if OUT.exists() or HAND.exists():raise FileExistsError('immutable output exists')
OUT.mkdir(parents=True);HAND.mkdir(parents=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads(RES.read_text());q=json.loads(TABLE.read_text())
if not r['passed'] or not q['passed'] or r['history_hash']!=sha(HIST):raise ValueError('unqualified input')
if json.loads(RENDER_FAIL.read_text())['accepted'] or json.loads(HAND_FAIL.read_text())['accepted']:raise ValueError('failure lineage mismatch')
d=np.load(HIST);t=d['time'];f=d['released_volume_fraction'];events=r['quadrature_event_times']
fig,ax=plt.subplots(figsize=(7.2,4.4),constrained_layout=True)
ax.plot(t,f,color='#0b7285',lw=2.3,label='finite prolate body')
for name,y,c in [('first_release',0,'#f08c00'),('half_release',.5,'#7048e8'),('complete_release',1,'#c92a2a')]:
 ax.scatter(events[name],y,s=42,color=c,zorder=3)
 ax.annotate(f"{name.replace('_',' ')}\n$t^*={events[name]:.5f}$",(events[name],y),
  xytext=(-68,14 if y<.8 else -42),textcoords='offset points',fontsize=8,color=c)
ax.set(xlabel='dimensionless time, $t^*$',ylabel='body volume beyond outlet plane',ylim=(-.04,1.08),
 title='Verified finite-body release through a symmetric two-grain throat')
ax.grid(alpha=.25);ax.legend(loc='upper left',frameon=False)
ax.text(.99,.04,'Aligned AR=2 prolate; centreline; no contact\nSingle body (1/1 released), not soil-scale retention',
 transform=ax.transAxes,ha='right',va='bottom',fontsize=8,color='#495057')
fig.savefig(OUT/'finite_body_release.png',dpi=220);plt.close(fig)
handoff={'status':'READY_FOR_COMPARISON_AND_EXTERNAL_VALIDATION_DESIGN',
 'comparison_or_validation_executed':False,'accepted_table':str(TABLE),'accepted_table_hash':sha(TABLE),
 'accepted_release':str(RES),'accepted_release_hash':sha(RES),'release_history_hash':sha(HIST),
 'render':str(OUT/'finite_body_release.png'),'render_hash':sha(OUT/'finite_body_release.png'),
 'failed_render_predecessor_hash':sha(RENDER_FAIL),'failed_handoff_predecessor_hash':sha(HAND_FAIL),
 'measured_case':{'shape':'prolate','aspect_ratio':2,'orientation':'aligned with flow','trajectory':'symmetry centreline',
  'released_bodies':1,'total_bodies':1,'release_fraction':1.0,'complete_release_time':events['complete_release']},
 'qualified_numerics':{'max_table_interpolation_error':q['max_interpolation_error'],
  'max_table_boundary_error':q['max_boundary_error'],'release_quadrature_relative_error':r['relative_quadrature_error']},
 'preserved_failures':['table_01 coarse-boundary and linear-interpolation failure','table_02 throat interpolation failure',
  'table_03 0.120% near-miss','release_01 JSON serialization failure','render_01 GUI-backend failure'],
 'claim_boundary':['one finite-body passage only; not a soil-scale release fraction',
  'no retention distribution, arbitrary orientation, contact, migration or clogging established',
  'no sphere-fibre comparison or external validation performed'],
 'next_stage_frozen_requirements':['matched outlet, initial ensemble, censoring, horizon and numerical gates for both shapes',
  'external validation data held independent of tuning'],'stop_point':'before shape comparison and validation'}
(HAND/'handoff.json').write_text(json.dumps(handoff,indent=2))
(HAND/'README.md').write_text('# Stage36BS pre-comparison handoff\n\nAligned AR=2 prolate passage is verified. '
 f"First, half, and complete release: t*={events['first_release']:.5f}, {events['half_release']:.5f}, "
 f"{events['complete_release']:.5f}.\n\nThis is a one-body benchmark, intentionally stopped before shape comparison and external validation.\n")
print(json.dumps(handoff,indent=2))
