"""Render only verified stored regression evidence, with unchanged thresholds."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import repair_regression_v1 as job
api=job.api
source=job.EVAL/'independent_evaluation_01/results.json'
r=api.read(source);d=api.read(job.DESIGN);job.verify(d)
out=job.EVAL/'render_01';out.mkdir(parents=True,exist_ok=False)
fig,axes=plt.subplots(1,2,figsize=(12,5.4),gridspec_kw={'width_ratios':[1.12,1]})
fig.subplots_adjust(left=.08,right=.97,top=.79,bottom=.23,wspace=.32)
fig.suptitle('Contact-solver repair: bounded trajectory regression',fontsize=17,fontweight='bold',y=.96)
fig.text(.5,.89,f"{sum(x['qualified'] for x in r['ledger'])}/9 trajectories complete and healthy | {sum(g['passed'] for g in r['groups'])}/3 timestep groups pass | no new physics",ha='center',fontsize=11)
names=['Saved fibre episode','Fresh sphere','Fresh fibre'];x=np.arange(3);width=.24
for j,(key,label,budget) in enumerate([('position_difference_over_b','Position / 0.02 b',.02),('apolar_axis_angle_rad','Axis / 0.01 rad',.01),('translational_velocity_relative_difference','Speed / 5%',.05)]):
    vals=[g.get('medium_fine',{}).get(key,np.nan)/budget for g in r['groups']]
    axes[0].bar(x+(j-1)*width,vals,width,label=label,color=['#156f87','#d69136','#658b4a'][j])
axes[0].axhline(1,color='#a83737',linestyle='--',linewidth=1,label='Acceptance limit')
axes[0].set_xticks(x,names,rotation=16,ha='right');axes[0].set_ylabel('Medium–fine difference / allowed error')
axes[0].set_title('Three timestep levels; no relaxed gates',fontsize=11);axes[0].legend(fontsize=8,loc='best');axes[0].grid(axis='y',alpha=.2)
for i,g in enumerate(r['groups']):
    costs=[next(v.get('runtime_s',0) for v in r['ledger'] if v['case_id']==n) for n in g['ids']]
    axes[1].plot([1,.5,.25],costs,'o-',label=names[i])
axes[1].set_xticks([.25,.5,1],['1/4','1/2','Base']);axes[1].set_xlabel('Timestep-cap multiplier');axes[1].set_ylabel('Measured integration time (s)')
axes[1].set_title('Bounded cost, not population projection',fontsize=11);axes[1].legend(fontsize=9);axes[1].grid(alpha=.2)
fig.text(.08,.075,'Scope: fixed sand, prescribed corrected flow, rigid particles, one-way forcing. 0.5-s numerical endpoint only.\nSaved episode starts from an inherited accepted checkpoint. No release fraction or experimental validation claimed.',fontsize=9,color='#444444')
for ext in ['png','svg']:fig.savefig(out/('repair_regression.'+ext),dpi=180)
api.write(out/'manifest.json',{'source_sha256':api.sha(source),'renderer_sha256':api.sha(__file__),'artifacts':{str(p):api.sha(p) for p in out.iterdir() if p.is_file()}})
print(out/'repair_regression.png')
