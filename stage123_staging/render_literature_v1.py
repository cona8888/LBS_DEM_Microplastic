"""Visualize archived experimental curves only, without a misleading DEM overlay."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import audit_literature_v1 as job
import json
source=job.OUT/'experimental_curves.json'
curves=json.loads(source.read_text());result=json.loads((job.OUT/'results.json').read_text())
assert result['data_extraction_passed'] and not result['empirical_model_validation_passed']
out=job.OUT.parent/'render_01';out.mkdir(parents=True,exist_ok=False)
fig,axs=plt.subplots(1,2,figsize=(12,6.1))
fig.subplots_adjust(left=.08,right=.97,top=.77,bottom=.30,wspace=.22)
fig.suptitle('Experimental fibre data recovered — not yet a matched validation',fontsize=16,fontweight='bold',y=.96)
fig.text(.5,.89,'Fouty & Engdahl (2024) | archived experimental CDFs | no model fitting or DEM overlay',ha='center',fontsize=11)
colors=['#176f83','#b4772b','#7e4d88','#303d48']
for i,ax in enumerate(axs,1):
    for row,color in zip([c for c in curves if c['pore_window']==i],colors):
        t=np.array(row['time_s']);y=np.array(row['experimental_processed_cdf'])
        ax.semilogx(t[1:],y[1:],label=row['label'],color=color,lw=2)
    ax.set(xlim=(.2,30),ylim=(0,1.02),xlabel='Archived travel time (s)',title=['First pore','Both pores'][i-1])
    ax.set_ylabel('Normalized cumulative passage probability');ax.grid(alpha=.2)
    ax.axhline(.5,color='#999',ls=':',lw=1)
    med=[r for r in result['rows'] if r['pore_window']==i]
    ax.text(.97,.10,'Median fibre / bead time\n'+', '.join(f"{r['t50_over_same_window_beads']:.2f}" for r in med[:3]),transform=ax.transAxes,ha='right',fontsize=9.5,bbox={'facecolor':'white','edgecolor':'#ccc','alpha':.9})
handles,labels=axs[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,.19),ncol=4,fontsize=10,frameon=False)
fig.text(.08,.12,'These injected-particle, centroid-passage curves are not whole-body release fractions from a soil inventory.\nGeometry, particle sizes, loading and flow regime differ from our present sand model.',fontsize=9.5)
fig.text(.08,.047,'Integrity note: archive median increase (8 mm vs 3 mm, both pores) = 15.3%; article text says about 35%.\nThe discrepancy is preserved and unresolved. Data DOI: 10.7273/000006421.',fontsize=9.2,color='#654431')
for ext in ['png','svg']:fig.savefig(out/('experimental_fibre_curves.'+ext),dpi=180)
job.write(out/'manifest.json',{'source_sha256':job.sha(source),'renderer_sha256':job.sha(__file__),'artifacts':{str(p):job.sha(p) for p in out.iterdir() if p.is_file()}})
print(out/'experimental_fibre_curves.png')
