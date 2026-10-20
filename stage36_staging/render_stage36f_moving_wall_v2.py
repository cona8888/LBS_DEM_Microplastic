"""Render saved CPU reference results, not a flow simulation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from moving_wall_reference_v1 import analytic
from verify_stage36d_wrench_transfer_v1 import ROOT,sha

base=ROOT/'stage36_evaluations/stage36f_moving_wall_20260906'
verification=base/'verification_01/verification.json'
report=json.loads(verification.read_text())
if report['passed'] is not True: raise RuntimeError('verification not passed')
for name,digest in report['artifact_hashes'].items():
    if sha(name)!=digest: raise RuntimeError('artifact changed')
data_path=base/'verification_01/flow_results.json'
data=json.loads(data_path.read_text())
output=base/'render_02';output.mkdir(exist_ok=False)
fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
s=np.linspace(0,1,300)
axes[0].plot(s,analytic(s,.1),color='#18334d',lw=2,label='Analytical transient')
for row in data['runs'][:3]:
    axes[0].plot(row['y_over_H'],np.array(row['profiles']['0.1'])/row['top_lu'],'.',label=f"N={row['n']}")
axes[0].set(xlabel='Height y/H',ylabel='Velocity u/U',title='Moving-wall flow at dimensionless time 0.1')
axes[0].legend(frameon=False,fontsize=9);axes[0].grid(alpha=.2)
n=np.array([r['n'] for r in data['runs'][:3]])
errors=np.array([r['transient_normalized_rms_error'] for r in data['runs'][:3]])
axes[1].loglog(n,errors,'o-',color='#007f78',label='Measured transient RMS error')
axes[1].loglog(n,errors[0]*(n[0]/n)**2,'--',color='gray',label='Second-order reference')
axes[1].set(xlabel='Fluid nodes across height, N',ylabel='Normalized RMS velocity error',title='Diffusive refinement: fixed physical problem')
axes[1].xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
axes[1].set_xticks(n,labels=n);axes[1].legend(frameon=False,fontsize=9);axes[1].grid(alpha=.2,which='both')
fig.suptitle('Stage36F | Planar sliding-wall benchmark — CPU FP64',fontsize=14,fontweight='bold')
fig.supxlabel('Fixed fluid domain. No moving fibre, refill scheme, soil transport or release prediction.',fontsize=9)
path=output/'couette_verification.png';fig.savefig(path,dpi=170);plt.close(fig)
manifest={'source_hashes':{str(Path(__file__).resolve()):sha(__file__),str(verification):sha(verification),str(data_path):sha(data_path)},
          'artifact_hashes':{str(path):sha(path)},'transient_rms_errors':errors.tolist(),
          'observed_orders':np.log(errors[:-1]/errors[1:]).tolist()}
# Store base-2 observed orders for each doubling of N.
manifest['observed_orders']=(np.log(errors[:-1]/errors[1:])/np.log(2)).tolist()
(output/'render_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
