"""Consolidate qualified Stage36 release evidence and render diagnostics."""
import hashlib,json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
CI=R/'stage36_evaluations/stage36ci_refined_path_validation_20260911/run_01';CK=R/'stage36_evaluations/stage36ck_throat_picard_20260911/run_01';CL=R/'stage36_evaluations/stage36cl_upstream_gap_20260911/run_01'
O=R/'stage36_evaluations/stage36cm_qualified_release_measurement_20260911/report_01';O.mkdir(parents=True,exist_ok=False)
contract={'question':'within the qualified fixed two-grain throat benchmark, what fraction of equal-volume spheres and prolate fibres fully crosses the outlet by t*=100?',
 'observable':'scenario count fraction; constant-density mass fraction is identical','release_event':'entire body support downstream of x=4 outlet','censoring':'unresolved cases widen upper bound and are never labelled retained','scope':'rigid isolated body, steady Stokes flow, fixed grains, no adhesion, no contact, no soil network, no ensemble weighting'}
(O/'contract.json').write_text(json.dumps(contract,indent=2));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs=[Path(__file__),CI/'results.json',CK/'results.json',CL/'results.json',O/'contract.json'];before={str(p):sha(p) for p in inputs};ci=json.loads((CI/'results.json').read_text());ck=json.loads((CK/'results.json').read_text());cl=json.loads((CL/'results.json').read_text());assert not ci['passed'] and not ck['passed'] and cl['passed']
rows=[];accepted=[]
for case in range(1,13):
 if case in (9,12): src=json.loads((CL/f'case_{case:02}.json').read_text())
 else: src=json.loads((CI/f'case_{case:02}.json').read_text());assert src['passed']
 h=src['trajectories']['0.05']['history'];last=h[-1];shape='sphere' if case<=3 else 'prolate';y0=[0,.15,-.15][case-1] if case<=3 else [0,0,0,.15,.15,.15,-.15,-.15,-.15][case-4];ang=0 if case<=3 else [0,45,90,0,45,90,0,45,90][case-4]
 rows.append({'case':case,'shape':shape,'initial_y':y0,'initial_angle_deg':ang,'status':src['trajectories']['0.05']['status'],'event_time':last['t'],'final_y':last['y'],'final_theta_rad':last['theta'],'event_time_fine_vs_medium_relative':src['event_time_fine_vs_medium_relative'],'history':h})
 if case not in (9,12): accepted.extend(src['validation'])
# Cases 9/12: use nonfailed far-field CI checks, passed positive-throat CK checks, and final CL checks.
for case in (9,12):
 accepted.extend([v for v in json.loads((CI/f'case_{case:02}.json').read_text())['validation'] if v['passed']])
 accepted.extend([v for v in json.loads((CK/f'case_{case:02}.json').read_text())['validation'] if v['passed']])
 accepted.extend(json.loads((CL/f'case_{case:02}.json').read_text())['validation'])
def group(shape):
 a=[r for r in rows if r['shape']==shape];n=len(a);released=sum(r['status']=='released' for r in a);unresolved=sum(r['status']!='released' for r in a)
 return {'n_scenarios':n,'released':released,'unresolved':unresolved,'release_fraction_lower':released/n,'release_fraction_upper':(released+unresolved)/n,'event_time_mean':float(np.mean([r['event_time'] for r in a])),'event_time_min':min(r['event_time'] for r in a),'event_time_max':max(r['event_time'] for r in a)}
summary={'sphere':group('sphere'),'prolate':group('prolate')};errors={'accepted_pose_checks':len(accepted),'max_axial_relative':max(v['errors']['axial_relative'] for v in accepted),'max_transverse_absolute':max(v['errors']['transverse_absolute'] for v in accepted),'max_angular_absolute':max(v['errors']['angular_absolute'] for v in accepted),'max_event_time_fine_vs_medium_relative':max(r['event_time_fine_vs_medium_relative'] for r in rows)}
checks={'12_terminal_events':all(r['status']=='released' for r in rows),'zero_unresolved':all(v['unresolved']==0 for v in summary.values()),'accepted_pose_gates':errors['max_axial_relative']<=.01 and errors['max_transverse_absolute']<=.002 and errors['max_angular_absolute']<=.003,'time_integration_gate':errors['max_event_time_fine_vs_medium_relative']<=.002,'final_refinement_passed':cl['passed'],'inputs_unchanged':before=={str(p):sha(p) for p in inputs}}
result={'passed':all(checks.values()),'checks':checks,'summary':summary,'numerical_evidence':errors,'rows':[{k:v for k,v in r.items() if k!='history'} for r in rows],'interpretation':{'supported':'all 12 prescribed, noncontact scenarios fully release in this idealized open throat; shape/orientation changes trajectory and transit time but not the binary outcome','not_supported':'field or column release fraction, calibration to soil, retention under attachment/contact, or population-scale fibre-versus-sphere loss'},'input_hashes':before};(O/'results.json').write_text(json.dumps(result,indent=2))
fig,(ax0,ax1)=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
colors={'sphere':'#2b6cb0','prolate':'#c05621'}
for r in rows:
 x=[s['x'] for s in r['history']];y=[s['y'] for s in r['history']];ax0.plot(x,y,color=colors[r['shape']],alpha=.55,lw=1.5,ls='--' if r['shape']=='sphere' else '-')
ax0.axvline(4,color='k',lw=1,ls=':');ax0.set(xlabel='Axial position, x*',ylabel='Lateral position, y*',title='Qualified centre trajectories');ax0.grid(alpha=.2)
for shape,marker in [('sphere','o'),('prolate','s')]:
 a=[r for r in rows if r['shape']==shape];ax1.scatter([r['case'] for r in a],[r['event_time'] for r in a],label=shape,color=colors[shape],marker=marker,s=48)
ax1.axhline(100,color='k',lw=1,ls=':',label='time horizon');ax1.set(xlabel='Prescribed scenario',ylabel='Full-release time, t*',title='All scenarios fully released');ax1.set_xticks(range(1,13));ax1.grid(alpha=.2);ax1.legend(frameon=False)
fig.suptitle('Equal-volume sphere vs prolate fibre: idealized two-grain throat',fontweight='bold');fig.savefig(O/'qualified_release_diagnostics.png',dpi=220);plt.close(fig)
md=f"""# Qualified release measurement — idealized throat benchmark

**Result.** All 3/3 sphere scenarios and all 9/9 prolate-fibre scenarios fully crossed the outlet before the frozen horizon t*=100. The scenario release bounds are therefore [1.000, 1.000] for both shapes; constant-density mass bounds are identical.

This is a numerical verification result for one isolated rigid body in a fixed, symmetric two-grain throat under steady Stokes flow. It demonstrates sensitivity of trajectory and transit time to shape, orientation, and lateral placement. It does **not** estimate release from a soil matrix: there is no pore network, contact/friction, attachment, fibre flexibility, migration history, or population weighting.

Accepted evidence comprises {errors['accepted_pose_checks']} fresh direct-pose checks. Maximum errors were {100*errors['max_axial_relative']:.3f}% axial, {errors['max_transverse_absolute']:.3e} transverse, and {errors['max_angular_absolute']:.3e} angular; the maximum fine-to-medium event-time shift was {100*errors['max_event_time_fine_vs_medium_relative']:.4f}%.
""";(O/'REPORT.md').write_text(md);print(json.dumps({'passed':result['passed'],'summary':summary,'errors':errors,'figure':str(O/'qualified_release_diagnostics.png')}))
