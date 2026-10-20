import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bm_tracer_release_20260911';out=root/'render_01';out.mkdir(exist_ok=False)
r=json.loads((root/'run_02/results.json').read_text())
if not r['passed']:raise ValueError('unqualified run')
with np.load(root/'run_02/dt0.005.npz') as d:p=d['path'];t=d['time'];c=d['release_count']
fig,axes=plt.subplots(1,2,figsize=(11,4.6),layout='constrained')
for j in range(0,81,4):
    mask=p[:,j,0]<=4.05;axes[0].plot(p[mask,j,0],p[mask,j,1],lw=.8,color='#287d9a')
axes[0].add_patch(plt.Circle((0,0),1,color='#555555'));axes[0].axvline(4,color='#b64735',ls='--',label='Outlet plane')
axes[0].set(xlim=(-3.2,4.4),ylim=(-3,3),aspect='equal',xlabel='x / grain radius',ylabel='y / grain radius',title='Point tracers around one fixed grain');axes[0].legend()
axes[1].step(t,c/81,where='post',color='#287d9a');axes[1].set(xlabel='Time / (radius / far-field speed)',ylabel='Released fraction of initial tracer count',ylim=(0,1),title='62 / 81 released by t*=20');axes[1].grid(alpha=.2)
fig.suptitle('Release-accounting benchmark — NOT finite-fibre or soil release',fontsize=12)
fig.savefig(out/'tracer_release.png',dpi=160);plt.close(fig)
