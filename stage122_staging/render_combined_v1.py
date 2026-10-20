"""Render failed coarse gates alongside unchanged refined gates and spatial sensitivity."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import refine_spheres_v1 as job
api=job.api
d=api.read(job.DESIGN);job.verify(d)
old=api.read(job.PRESULT);new=api.read(job.EVAL/'independent_evaluation_01/results.json')
api.require(new['passed'],'refinement not qualified')
groups=[new['groups'][0],old['groups'][1],new['groups'][1],old['groups'][3]]
api.require(all(g['passed'] for g in groups),'combined triplets not qualified')
out=job.EVAL/'render_01';out.mkdir(parents=True,exist_ok=False)
fig,axs=plt.subplots(1,2,figsize=(12,5.8),gridspec_kw={'width_ratios':[1.15,1]})
fig.subplots_adjust(left=.08,right=.97,top=.79,bottom=.26,wspace=.31)
fig.suptitle('Repaired transport solver: matched 0.5-s checks',fontsize=17,fontweight='bold',y=.96)
fig.text(.5,.89,'18 new trajectories completed | 4/4 updated timestep groups pass | spatial qualification remains open',ha='center',fontsize=10.5)
x=np.arange(4);w=.23
for j,(key,label,budget) in enumerate([('position_difference_over_b','Position / 0.02 b',.02),('apolar_axis_angle_rad','Axis / 0.01 rad',.01),('translational_velocity_relative_difference','Velocity / 5%',.05)]):
    axs[0].bar(x+(j-1)*w,[g['medium_fine'][key]/budget for g in groups],w,label=label,color=['#176f83','#d58c31','#57844a'][j])
axs[0].axhline(1,color='#a63737',ls='--',label='Unchanged limit')
axs[0].set_ylim(0,1.13);axs[0].set_ylabel('Medium–fine difference / acceptance budget')
axs[0].set_xticks(x,['CPD2\nsphere','CPD2\nfibre','CPD4\nsphere','CPD4\nfibre']);axs[0].set_title('Temporal verification',fontsize=12)
axs[0].legend(fontsize=8,ncol=2,loc='lower center',bbox_to_anchor=(.5,-.40));axs[0].grid(axis='y',alpha=.18)
axs[1].axis('off')
sp=[new['spatial_sensitivity'][0],old['spatial_sensitivity'][1]]
table=axs[1].table(cellText=[[name,f"{r['position_difference_over_b']:.4f}",f"{r['apolar_axis_angle_rad']:.4f}",f"{100*r['translational_velocity_relative_difference']:.2f}%"] for name,r in zip(['Sphere','Fibre'],sp)],
    colLabels=['Shape','Position / b','Axis (rad)','Velocity'],cellLoc='center',colWidths=[.22,.29,.27,.22],bbox=[0,.47,1,.38])
table.auto_set_font_size(False);table.set_fontsize(10)
for (r,c),cell in table.get_celld().items():
    cell.set_edgecolor('#d4dde3')
    if r==0:cell.set_facecolor('#e5eef3');cell.set_text_props(weight='bold')
axs[1].set_title('Finest CPD2 vs CPD4 response',fontsize=12,pad=9)
axs[1].text(0,.33,'Matched nominal forcing; achieved speeds differ by 0.59%.\nThese are sensitivity measurements, not a spatial pass.',fontsize=10,va='top')
axs[1].text(0,.15,'Stage121 coarse sphere position gates failed.\nStage122 refined 1/4–1/8–1/16 caps; tolerances unchanged.',fontsize=9.5,color='#555',va='top')
fig.text(.08,.045,'Fixed sand; rigid particles; corrected steady, one-way flow. All cases present at this finite endpoint.\nNo population export fraction, full-path convergence or experimental validation is established.',fontsize=9,color='#444')
for ext in ['png','svg']:fig.savefig(out/('matched_resolution.'+ext),dpi=180)
api.write(out/'manifest.json',{'source_hashes':{str(job.PRESULT):api.sha(job.PRESULT),str(job.EVAL/'independent_evaluation_01/results.json'):api.sha(job.EVAL/'independent_evaluation_01/results.json')},'renderer_sha256':api.sha(__file__),'artifacts':{str(p):api.sha(p) for p in out.iterdir() if p.is_file()}})
print(out/'matched_resolution.png')
