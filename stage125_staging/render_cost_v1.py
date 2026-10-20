"""Plot measured cost and conditional scenarios without a convergence claim."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import spatial_cost_v1 as job

d=job.read(job.DESIGN)
path=job.EVAL/'independent_evaluation_01/results.json'
r=job.read(path)
done=job.read(path.with_name('completion.json'))
job.require(r['passed'] and done['results_sha256']==job.sha(path),'unverified cost result')
out=job.EVAL/'render_01';out.mkdir(parents=True,exist_ok=False)
fig,axes=plt.subplots(1,2,figsize=(11.5,5.6))
fig.subplots_adjust(left=.08,right=.97,bottom=.31,top=.78,wspace=.36)
fig.suptitle('A third grid fits in memory; convergence cost is still the gate',fontsize=16,weight='bold',y=.96)
fig.text(.5,.865,f"CPD6 pilot: 417 steps | {r['median_kernel_seconds_per_step']:.3f} s/step | {r['device_GiB']:.2f} GiB device allocation",ha='center',fontsize=12)
cpds=[2,4,6,8];ns=[93,186,279,372]
memory=[job.device_bytes(n)/1024**3 for n in ns]
axes[0].bar(range(4),memory,color=['#718695','#718695','#26877f','#c4cbcf'])
for i,v in enumerate(memory):axes[0].text(i,v+.12,f'{v:.2f}',ha='center',fontsize=10)
axes[0].set_xticks(range(4),[f'CPD{c}\n{n}$^3$ cells' for c,n in zip(cpds,ns)])
axes[0].set_ylabel('GPU allocation (GiB)')
axes[0].set_title('Allocation formula; CPD6 also measured',fontsize=11)
axes[0].set_ylim(0,9)
sc=r['conditional_cost_scenarios']
v=[x['kernel_hours_with_margin'] for x in sc]
axes[1].bar(range(3),v,color=['#26877f' if x['within_six_hour_kernel_budget'] else '#bd743d' for x in sc])
axes[1].axhline(6,color='#394653',ls='--',lw=1.5)
axes[1].text(-.45,6.25,'6-hour total study budget',fontsize=9,color='#394653')
for i,y in enumerate(v):axes[1].text(i,y+.25,f'{y:.1f} h',ha='center',fontsize=10)
axes[1].set_xticks(range(3),[f"{x['assumed_steps']:,}" for x in sc])
axes[1].set_xlabel('Assumed number of CPD6 steps — not predicted convergence')
axes[1].set_ylabel('Conditional kernel time (hours)')
axes[1].set_title('Slowest timed block × steps × 1.25 margin',fontsize=11)
axes[1].set_ylim(0,max(v)*1.15)
for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.text(.08,.17,'The cold-start pilot passed numerical-health and sampled CPU/GPU transition checks.',fontsize=10)
fig.text(.08,.115,'It is not a steady or mean-matched flow field. Timings exclude future initialization, host diagnostics, output and forcing corrections.',fontsize=9,color='#555555')
fig.text(.08,.07,'Next: a bounded CPD4-initialized relaxation to measure convergence cost. Spatial and experimental validation remain open.',fontsize=9,color='#555555')
for suffix in ['png','svg']:fig.savefig(out/f'third_grid_cost.{suffix}',dpi=180)
plt.close(fig)
job.write(out/'manifest.json',{'results':job.bind(path),'renderer':job.bind(__file__),
          'artifacts':{str(p):job.sha(p) for p in out.iterdir() if p.is_file()}})
print(out,flush=True)
