"""Evaluate corrected matrix-release pilot without interpreting interception as retention."""
import csv,hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=R/'stage36_runs/stage36cr_matrix_release_pilot_corrected_20260911/pilot_01';T=R/'stage36_evaluations/stage36cs_corrected_tracer_limit_20260911/run_01';O=R/'stage36_evaluations/stage36ct_matrix_release_evaluation_20260911/evaluation_01';O.mkdir(parents=True,exist_ok=False)
contract={'role':'prediction/evaluation, not external validation','primary':'certified-release lower bound and interception-censored upper bound','paired_comparison':'common initial centres; report discordant counts, no monotonicity','tracer_conditioning':'secondary analysis restricted to starts with certified zero-size release'};(O/'contract.json').write_text(json.dumps(contract,indent=2));pr=json.loads((P/'results.json').read_text());tr=json.loads((T/'results.json').read_text());assert pr['passed'] and tr['passed'];body=json.loads((P/'trajectories_dx_0p1.json').read_text());trace=json.loads((T/'tracers_dx_0p1.json').read_text());starts={s['id']:s for s in json.loads((P/'initial_ensemble.json').read_text())};by={(r['shape'],r['id']):r for r in body};viable={r['id'] for r in trace if r['status']=='released'}
pairs=[]
for i in sorted(starts):
 s=by['sphere',i]['status']=='released';f=by['prolate',i]['status']=='released';pairs.append({'id':i,'sphere_released':s,'prolate_released':f,'tracer_viable':i in viable,'outcome':'both' if s and f else 'sphere_only' if s else 'prolate_only' if f else 'neither','streamwise_stratum':starts[i]['stratum'][0],'clearance_stratum':starts[i]['stratum'][1]})
pc={k:sum(p['outcome']==k for p in pairs) for k in ('both','sphere_only','prolate_only','neither')};conditional={}
for shape in ('sphere','prolate'):
 rr=[by[shape,i] for i in viable];rel=sum(r['status']=='released' for r in rr);conditional[shape]={'tracer_viable_n':len(rr),'certified_released':rel,'conditional_lower':rel/len(rr),'conditional_upper':1.0}
strata=[]
for axis,key in [('streamwise','streamwise_stratum'),('clearance','clearance_stratum')]:
 for level in range(3):
  ids=[p['id'] for p in pairs if p[key]==level]
  for shape in ('sphere','prolate'):
   strata.append({'axis':axis,'level':level,'shape':shape,'n':len(ids),'released':sum(by[shape,i]['status']=='released' for i in ids),'lower_fraction':sum(by[shape,i]['status']=='released' for i in ids)/len(ids)})
summary={'passed':True,'evidence_class':'numerically verified reduced-model prediction','all_start_release_bounds':{s:{'lower':pr['summary_fine'][s]['release_lower'],'upper':pr['summary_fine'][s]['release_upper']} for s in ('sphere','prolate')},'tracer_limit':tr['fine_fractions'],'conditional_on_tracer_viable':conditional,'paired_outcomes':pc,'certified_lower_difference_prolate_minus_sphere':pr['summary_fine']['prolate']['release_lower']-pr['summary_fine']['sphere']['release_lower'],'interpretation':{'supported':'a small certified fraction crosses without conservative interception; AR=4 fibre lower bound is one of 64 below the equal-volume sphere in this realization','not_supported':'intercepted bodies are retained, the true release fraction equals either bound, or a general sphere-fibre effect exists'},'numerical':pr['numerical'],'strata':strata}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();inputs=[Path(__file__),P/'results.json',P/'trajectories_dx_0p1.json',P/'initial_ensemble.json',T/'results.json',T/'tracers_dx_0p1.json',O/'contract.json'];summary['input_hashes']={str(p):sha(p) for p in inputs};(O/'results.json').write_text(json.dumps(summary,indent=2))
with (O/'paired_outcomes.csv').open('w',newline='') as f: w=csv.DictWriter(f,fieldnames=pairs[0]);w.writeheader();w.writerows(pairs)
fig,axs=plt.subplots(1,3,figsize=(13,4.3),constrained_layout=True);colors={'sphere':'#2b6cb0','prolate':'#c05621'}
for j,s in enumerate(('sphere','prolate')):
 lo=summary['all_start_release_bounds'][s]['lower'];hi=summary['all_start_release_bounds'][s]['upper'];axs[0].plot([j,j],[lo,hi],color=colors[s],lw=8,alpha=.25);axs[0].scatter(j,lo,color=colors[s],s=70,zorder=3);axs[0].text(j,lo+.035,f'{lo:.3f}',ha='center',color=colors[s],fontweight='bold')
axs[0].set_xticks([0,1],['sphere','AR=4 fibre']);axs[0].set_ylim(0,1.06);axs[0].set_ylabel('Release fraction');axs[0].set_title('Certified lower → censored upper');axs[0].grid(axis='y',alpha=.2)
labels=['both','sphere only','fibre only','neither'];vals=[pc['both'],pc['sphere_only'],pc['prolate_only'],pc['neither']];axs[1].bar(labels,vals,color=['#4c956c','#2b6cb0','#c05621','#718096']);axs[1].set_ylabel('Paired starts (n)');axs[1].set_title('Common-start outcomes');axs[1].tick_params(axis='x',rotation=25);axs[1].grid(axis='y',alpha=.2)
for shape,ls in [('sphere','-'),('prolate','--')]:
 times=sorted(r['time_pv'] for r in body if r['shape']==shape and r['status']=='released');x=[0]+times+[.25];y=[0]+[i/64 for i in range(1,len(times)+1)]+[len(times)/64];axs[2].step(x,y,where='post',label=shape,color=colors[shape],ls=ls,lw=2)
axs[2].set(xlabel='Pore volumes elapsed',ylabel='Certified cumulative release',title='Early certified release');axs[2].set_xlim(0,.25);axs[2].set_ylim(0,.15);axs[2].grid(alpha=.2);axs[2].legend(frameon=False)
fig.suptitle('Resident microplastic release — one fixed LBS realization',fontweight='bold');fig.savefig(O/'matrix_release_bounds.png',dpi=220);plt.close(fig)
(O/'REPORT.md').write_text(f"# Stage36CT matrix-release pilot\n\nAt seven pore volumes, certified release was 8/64 ({8/64:.2%}) for equal-volume spheres and 7/64 ({7/64:.2%}) for AR=4 fibres. Conservative interception leaves both upper bounds at 100%; it is not evidence of permanent retention. The corrected tracer limit released 59/64 ({59/64:.2%}) starts. Conditional on those carrier-viable starts, the lower bounds are {conditional['sphere']['conditional_lower']:.2%} and {conditional['prolate']['conditional_lower']:.2%}. The one-start paired difference is exploratory and does not establish a general shape effect.\n");print(json.dumps({'passed':True,'paired':pc,'conditional':conditional,'figure':str(O/'matrix_release_bounds.png')}))
