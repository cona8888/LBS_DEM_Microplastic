"""Publication-readable zoomed render; no physical or numerical rerun."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];B=R/'stage36_evaluations/stage36cm_qualified_release_measurement_20260911/report_01';R2=R/'stage36_evaluations/stage36cm_qualified_release_measurement_20260911/render_02';CI=R/'stage36_evaluations/stage36ci_refined_path_validation_20260911/run_01';CL=R/'stage36_evaluations/stage36cl_upstream_gap_20260911/run_01';O=R/'stage36_evaluations/stage36cm_qualified_release_measurement_20260911/render_03';O.mkdir(parents=True,exist_ok=False)
contract={'role':'visual QA revision only','reason':'zoom event-time axis while retaining explicit horizon annotation','physics_rerun':False};(O/'contract.json').write_text(json.dumps(contract,indent=2));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs=[Path(__file__),B/'results.json',R2/'results.json',CI/'results.json',CL/'results.json',O/'contract.json'];before={str(p):sha(p) for p in inputs};result=json.loads((B/'results.json').read_text());assert result['passed'];rows=[]
for case in range(1,13):
 meta=next(r for r in result['rows'] if r['case']==case);src=json.loads(((CL if case in (9,12) else CI)/f'case_{case:02}.json').read_text());rows.append((meta,src['trajectories']['0.05']['history']))
fig,(ax0,ax1)=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True);colors={'sphere':'#2b6cb0','prolate':'#c05621'}
for r,h in rows:ax0.plot([s['x'] for s in h],[s['y'] for s in h],color=colors[r['shape']],alpha=.58,lw=1.6,ls='--' if r['shape']=='sphere' else '-')
ax0.axvline(4,color='k',lw=1,ls=':');ax0.text(3.94,.183,'outlet',ha='right',va='top',fontsize=9);ax0.set(xlabel='Axial position, x*',ylabel='Lateral position, y*',title='Qualified centre trajectories');ax0.grid(alpha=.2)
for shape,marker in [('sphere','o'),('prolate','s')]:
 a=[r for r,_ in rows if r['shape']==shape];ax1.scatter([r['case'] for r in a],[r['event_time'] for r in a],label=shape,color=colors[shape],marker=marker,s=52,zorder=3)
ax1.set(xlabel='Prescribed scenario',ylabel='Full-release time, t*',title='Transit-time differences (all released)');ax1.set_xticks(range(1,13));ax1.set_ylim(33.45,34.58);ax1.grid(alpha=.2);ax1.legend(frameon=False,loc='upper left');ax1.text(.98,.04,'Frozen horizon: t*=100 (not shown)',transform=ax1.transAxes,ha='right',fontsize=9)
fig.suptitle('Equal-volume sphere vs prolate fibre: idealized two-grain throat',fontweight='bold');fig.savefig(O/'qualified_release_diagnostics.png',dpi=220);plt.close(fig)
out={'passed':True,'physics_rerun':False,'source_result_hash':sha(B/'results.json'),'figure_hash':sha(O/'qualified_release_diagnostics.png'),'inputs_unchanged':before=={str(p):sha(p) for p in inputs}};(O/'results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
