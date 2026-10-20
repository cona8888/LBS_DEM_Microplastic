"""Visually corrected two-panel release figure and final pre-comparison handoff."""
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
PRIOR=ROOT/'stage36_evaluations/stage36bs_precomparison_handoff_20260911/handoff_02/handoff.json'
VFAIL=ROOT/'stage36_renders/stage36br_finite_body_release_20260911/render_02/visual_qc.json'
OUT=ROOT/'stage36_renders/stage36br_finite_body_release_20260911/render_03'
HAND=ROOT/'stage36_evaluations/stage36bs_precomparison_handoff_20260911/handoff_03'
if OUT.exists() or HAND.exists():raise FileExistsError('immutable output exists')
OUT.mkdir(parents=True);HAND.mkdir(parents=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads(RES.read_text());q=json.loads(TABLE.read_text());prior=json.loads(PRIOR.read_text())
if not r['passed'] or not q['passed'] or json.loads(VFAIL.read_text())['passed']:raise ValueError('lineage mismatch')
d=np.load(HIST);t=d['time'];f=d['released_volume_fraction'];e=r['quadrature_event_times']
fig,(a,b)=plt.subplots(1,2,figsize=(9.2,4.35),gridspec_kw={'width_ratios':[1,1.55]},constrained_layout=True)
for ax in (a,b):
 ax.plot(t,f,color='#0b7285',lw=2.3);ax.grid(alpha=.25);ax.set_ylim(-.05,1.08)
a.set(xlabel='dimensionless time, $t^*$',ylabel='body volume beyond outlet',title='Full passage history')
b.set(xlabel='dimensionless time, $t^*$',title='Outlet crossing (expanded)',xlim=(32.72,33.82))
for name,y,c,off in [('first_release',0,'#f08c00',(8,12)),('half_release',.5,'#7048e8',(8,10)),
                     ('complete_release',1,'#c92a2a',(-118,-35))]:
 b.scatter(e[name],y,s=38,color=c,zorder=3)
 b.annotate(f"{name.replace('_',' ')}\n$t^*={e[name]:.5f}$",(e[name],y),xytext=off,
  textcoords='offset points',fontsize=8,color=c)
fig.suptitle('Verified release of one aligned AR=2 prolate through a symmetric two-grain throat',fontsize=14)
fig.text(.5,.005,'Centreline, positive clearance, no contact  |  1/1 released  |  benchmark only—not soil-scale retention',
 ha='center',fontsize=8,color='#495057')
fig.savefig(OUT/'finite_body_release.png',dpi=220);plt.close(fig)
handoff=dict(prior)
handoff.update({'render':str(OUT/'finite_body_release.png'),'render_hash':sha(OUT/'finite_body_release.png'),
 'prior_handoff_hash':sha(PRIOR),'prior_render_visual_qc_hash':sha(VFAIL),
 'visual_qc':'pending independent visual inspection','stop_point':'before shape comparison and validation'})
(HAND/'handoff.json').write_text(json.dumps(handoff,indent=2))
(HAND/'README.md').write_text('# Stage36BS pre-comparison handoff\n\nOne aligned AR=2 prolate finite-body passage is numerically verified. '
 f"First, half and complete release occur at t*={e['first_release']:.5f}, {e['half_release']:.5f}, and {e['complete_release']:.5f}.\n\n"
 'Scope stops before sphere–fibre comparison and external validation. This benchmark is not a soil-scale release fraction.\n')
print(json.dumps({'handoff':str(HAND/'handoff.json'),'render':str(OUT/'finite_body_release.png'),
 'render_hash':handoff['render_hash']},indent=2))
