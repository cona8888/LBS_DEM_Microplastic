"""Render the bounded CPD6 relaxation without implying convergence."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage126_staging'))
import cpd6_relaxation_v2 as entry
job=entry.v1

r=job.read(job.EVAL/'independent_evaluation_02/results.json')
raw=job.read(job.RUN/'stage126_s2_f1p0_cpd6_bounded/result.json')
job.require(r['passed'] and not r['checks']['steady_gate_passed'],'unexpected disposition')
rows=raw['rows'];regular=[x for x in rows if x['step']%257==0];adj=rows[-8:]
out=job.EVAL/'render_01';out.mkdir(parents=True,exist_ok=False)
fig,ax=plt.subplots(1,2,figsize=(12,5.8));fig.subplots_adjust(left=.09,right=.97,bottom=.28,top=.78,wspace=.34)
fig.suptitle('CPD6 bounded relaxation: healthy, but not stationary',fontsize=17,weight='bold',y=.96)
fig.text(.5,.86,f"4,096 steps | {r['runtime_seconds']/60:.1f} min | steady gate failed | mean error {100*r['mean_relative_error']:+.2f}%",ha='center',fontsize=12)
ax[0].semilogy([x['step'] for x in regular],[x['field_change_relative_l2'] for x in regular],marker='o',color='#376a84')
ax[0].axhline(5e-5,color='#b55d3a',ls='--',label='required 5×10⁻⁵')
ax[0].set(xlabel='LBM step',ylabel='Spaced field change (relative L2)',title='Long-window field change plateaus')
ax[0].legend(frameon=False);ax[0].grid(alpha=.2)
colors=['#346a82' if x['step']%2==0 else '#c37a35' for x in adj]
ax[1].bar([str(x['step']) for x in adj],[x['u_superficial'] for x in adj],color=colors)
ax[1].tick_params(axis='x',rotation=45);ax[1].set_ylabel('Superficial velocity (lattice units)')
ax[1].set_title(f"Persistent odd/even difference: {100*r['final_parity_superficial_gap_relative']:.4f}%")
ax[1].grid(axis='y',alpha=.2)
fig.text(.09,.16,'Blue/orange bars are even/odd consecutive states. Health, balance, density, Mach and CPU spot checks passed.',fontsize=9.5)
fig.text(.09,.105,'This is a preserved failed steady-state gate, not a permeability field, spatial-convergence result or transport input.',fontsize=9.5,color='#555')
fig.text(.09,.06,'Next: diagnose and remove the initialization parity mode within a separately frozen bounded test; no automatic extension.',fontsize=9.5,color='#555')
for suffix in ['png','svg']:fig.savefig(out/f'cpd6_bounded_relaxation.{suffix}',dpi=180)
plt.close(fig)
job.write(out/'manifest.json',{'results':job.bind(job.EVAL/'independent_evaluation_02/results.json'),'renderer':job.bind(__file__),
  'artifacts':{str(p):job.sha(p) for p in out.iterdir() if p.is_file()}})
