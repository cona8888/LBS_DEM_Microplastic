"""Render accepted Stage36BR finite-body release and write pre-comparison handoff."""
import hashlib,json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RES=ROOT/'stage36_evaluations/stage36br_finite_body_release_20260911/release_02/results.json'
HIST=ROOT/'stage36_evaluations/stage36br_finite_body_release_20260911/release_02/release_history.npz'
TABLE=ROOT/'stage36_evaluations/stage36bq_throat_table_20260911/table_04/results.json'
OUT=ROOT/'stage36_renders/stage36br_finite_body_release_20260911/render_01'
HAND=ROOT/'stage36_evaluations/stage36bs_precomparison_handoff_20260911/handoff_01'
if OUT.exists() or HAND.exists():raise FileExistsError('immutable output exists')
OUT.mkdir(parents=True);HAND.mkdir(parents=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads(RES.read_text());q=json.loads(TABLE.read_text())
if not r['passed'] or not q['passed'] or r['history_hash']!=sha(HIST):raise ValueError('unqualified input')
d=np.load(HIST);t=d['time'];x=d['centre_x'];f=d['released_volume_fraction']
fig,ax=plt.subplots(figsize=(7.2,4.4),constrained_layout=True)
ax.plot(t,f,color='#0b7285',lw=2.3,label='finite prolate body')
events=r['quadrature_event_times']
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
render_hash=sha(OUT/'finite_body_release.png')
handoff={
 'status':'READY_FOR_COMPARISON_AND_EXTERNAL_VALIDATION_DESIGN',
 'comparison_or_validation_executed':False,
 'accepted_table':str(TABLE),'accepted_table_hash':sha(TABLE),
 'accepted_release':str(RES),'accepted_release_hash':sha(RES),
 'release_history_hash':sha(HIST),'render_hash':render_hash,
 'measured_case':{'shape':'prolate','aspect_ratio':2,'orientation':'aligned with flow',
                  'trajectory':'symmetry centreline','released_bodies':1,'total_bodies':1,
                  'release_fraction':1.0,'complete_release_time':events['complete_release']},
 'qualified_numerics':{'max_table_interpolation_error':q['max_interpolation_error'],
                       'max_table_boundary_error':q['max_boundary_error'],
                       'release_quadrature_relative_error':r['relative_quadrature_error']},
 'preserved_failures':['table_01 coarse-boundary and linear-interpolation failure',
                       'table_02 unresolved throat interpolation failure',
                       'table_03 0.120% near-miss at x=0.625',
                       'release_01 JSON serialization failure'],
 'claim_boundary':['This verifies one finite-body passage, not a soil-scale release fraction.',
                   'No retention distribution, arbitrary orientation, contact, migration, or clogging is established.',
                   'No sphere-fibre comparison and no literature/experimental validation has been performed here.'],
 'next_stage_frozen_inputs':['sphere and fibre release definitions must use the same outlet, initial ensemble, censoring, time horizon and numerical gates',
                             'external validation data must remain independent of numerical tuning'],
 'stop_point':'before shape comparison and validation'}
(HAND/'handoff.json').write_text(json.dumps(handoff,indent=2))
(HAND/'README.md').write_text(
 '# Stage36BS pre-comparison handoff\n\n'
 'The aligned AR=2 prolate finite body clears the symmetric two-grain throat. '
 f"First, half, and complete release occur at t*={events['first_release']:.5f}, "
 f"{events['half_release']:.5f}, and {events['complete_release']:.5f}.\n\n"
 'This is a verified one-body benchmark only. It is intentionally stopped before sphere–fibre comparison '
 'and before literature or experimental validation. A contamination-release claim requires a matched population '
 'ensemble with orientation, lateral placement, contact/retention and censoring rules.\n')
print(json.dumps(handoff,indent=2))
