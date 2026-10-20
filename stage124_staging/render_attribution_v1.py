"""Scientific diagnostic bars with explicitly non-statistical refinement proxies."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import mean_offset_diagnostic_v1 as job
api=job.api
source=job.EVAL/'independent_evaluation_01/results.json'
d=api.read(job.DESIGN);job.verify(d);r=api.read(source)
api.require(r['passed'] and r['attribution']['status']=='finite_level_attribution_complete','unqualified diagnostic')
out=job.EVAL/'render_01';out.mkdir(parents=True,exist_ok=False)
fig,axes=plt.subplots(1,3,figsize=(13,6.2))
fig.subplots_adjust(left=.065,right=.98,top=.78,bottom=.30,wspace=.33)
fig.suptitle('Does the 0.59% mean-flow mismatch explain the response gap?',fontsize=16,fontweight='bold',y=.96)
fig.text(.5,.89,'Six mean-matched diagnostic trajectories | inherited physical laws and acceptance limits | 0.5-s sentinel only',ha='center',fontsize=10.5)
colors=['#46697f','#d69738','#438475'];x=np.arange(2);width=.24
for ax,key,title,mult in zip(axes,['position','velocity','axis'],['Position difference / minor radius','Velocity difference (% of fixed scale)','Apolar axis difference (rad)'],[1,100,1]):
    for j,(metric,label) in enumerate([('total_difference','Original CPD2–CPD4'),('amplitude_effect','Mean adjustment only'),('remaining_difference','Remaining difference')]):
        vals=[];err=[]
        for row in r['attribution']['rows']:
            z=row['metrics'][key];e=z['twice_adjacent_level_differences'];vals.append(z[metric]*mult)
            pair=[('A','B'),('A','C'),('C','B')][j];err.append(sum(e[k] for k in pair)*mult)
        ax.bar(x+(j-1)*width,vals,width,color=colors[j],label=label)
        # Clip displayed lower proxy at zero; these are not confidence intervals.
        ax.errorbar(x+(j-1)*width,vals,yerr=[np.minimum(vals,err),err],fmt='none',ecolor='#263641',elinewidth=.8,capsize=2)
    ax.set_xticks(x,['Sphere','AR4 fibre']);ax.set_ylabel(title);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,.17),ncol=3,frameon=False,fontsize=10)
fig.text(.065,.11,'Whiskers: sums of twice the adjacent medium–fine timestep differences. These are diagnostic noise proxies, not confidence bounds.',fontsize=9)
fig.text(.065,.045,'The adjusted CPD2 field is a counterfactual prescribed field, not a newly verified flow solution.\nNo spatial-convergence, population-export or experimental-validation claim follows from this comparison.',fontsize=9,color='#444')
for ext in ['png','svg']:fig.savefig(out/('mean_offset_attribution.'+ext),dpi=180)
api.write(out/'manifest.json',{'source_sha256':api.sha(source),'renderer_sha256':api.sha(__file__),'artifacts':{str(p):api.sha(p) for p in out.iterdir() if p.is_file()}})
print(out/'mean_offset_attribution.png')
