"""Headless recovery render of accepted Stage36CM numerical results."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];B=R/'stage36_evaluations/stage36cm_qualified_release_measurement_20260911/report_01';CI=R/'stage36_evaluations/stage36ci_refined_path_validation_20260911/run_01';CL=R/'stage36_evaluations/stage36cl_upstream_gap_20260911/run_01';O=R/'stage36_evaluations/stage36cm_qualified_release_measurement_20260911/render_02';O.mkdir(parents=True,exist_ok=False)
contract={'role':'headless render recovery only','physics_rerun':False,'numerical_source':str(B/'results.json')};(O/'contract.json').write_text(json.dumps(contract,indent=2));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs=[Path(__file__),B/'results.json',B/'failure.json',CI/'results.json',CL/'results.json',O/'contract.json'];before={str(p):sha(p) for p in inputs};result=json.loads((B/'results.json').read_text());assert result['passed'];rows=[]
for case in range(1,13):
 src=json.loads(((CL if case in (9,12) else CI)/f'case_{case:02}.json').read_text());meta=next(r for r in result['rows'] if r['case']==case);rows.append((meta,src['trajectories']['0.05']['history']))
fig,(ax0,ax1)=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True);colors={'sphere':'#2b6cb0','prolate':'#c05621'}
for r,h in rows:ax0.plot([s['x'] for s in h],[s['y'] for s in h],color=colors[r['shape']],alpha=.58,lw=1.6,ls='--' if r['shape']=='sphere' else '-')
ax0.axvline(4,color='k',lw=1,ls=':');ax0.set(xlabel='Axial position, x*',ylabel='Lateral position, y*',title='Qualified centre trajectories');ax0.grid(alpha=.2)
for shape,marker in [('sphere','o'),('prolate','s')]:
 a=[r for r,_ in rows if r['shape']==shape];ax1.scatter([r['case'] for r in a],[r['event_time'] for r in a],label=shape,color=colors[shape],marker=marker,s=48)
ax1.axhline(100,color='k',lw=1,ls=':',label='time horizon');ax1.set(xlabel='Prescribed scenario',ylabel='Full-release time, t*',title='All 12 scenarios fully released');ax1.set_xticks(range(1,13));ax1.set_ylim(32.8,100.8);ax1.grid(alpha=.2);ax1.legend(frameon=False,loc='upper right');fig.suptitle('Equal-volume sphere vs prolate fibre: idealized two-grain throat',fontweight='bold');fig.savefig(O/'qualified_release_diagnostics.png',dpi=220);plt.close(fig)
summary={'passed':True,'physics_rerun':False,'source_result_hash':sha(B/'results.json'),'figure_hash':sha(O/'qualified_release_diagnostics.png'),'inputs_unchanged':before=={str(p):sha(p) for p in inputs}};(O/'results.json').write_text(json.dumps(summary,indent=2));(O/'REPORT.md').write_text(f"# Qualified release measurement\n\nAll 3/3 sphere and 9/9 prolate scenarios fully released by t*=100. Bounds: [1.000, 1.000] for each shape. Mean event times were {result['summary']['sphere']['event_time_mean']:.3f} (sphere) and {result['summary']['prolate']['event_time_mean']:.3f} (prolate). This applies only to the isolated, rigid-body, fixed two-grain throat benchmark; it is not a soil-matrix release estimate.\n");print(json.dumps(summary))
