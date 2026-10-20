"""Independent snapshot inventory audit and finite-body release plot."""
import json,hashlib,platform
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bo_finite_release_20260911';run=root/'run_01';out=root/'audit_03';out.mkdir(exist_ok=False)
r=json.loads((root/'evaluation_01/results.json').read_text())
if not r['passed']:raise ValueError('failed run')
checks={};maxmass=0.;minimum=100.;histories={}
for n in [12,24,48]:
    with np.load(run/f'path_{n}.npz',allow_pickle=False) as d:p=d['position'];Q=d['orientation']
    h=np.linalg.norm(Q[:,0,:]*[.2,.1,.1],axis=1)
    def cdf(plane):
        s=np.clip((plane-p[:,0])/h,-1,1);return .5+.75*s-.25*s**3
    up=cdf(-4);down=1-cdf(4);inside=cdf(4)-cdf(-4)
    trace=json.loads((run/f'trace_{n}.json').read_text());times=np.array([v['t'] for v in trace['rows']])
    checks[f'ledger_{n}']=bool(np.max(abs(down-np.array([v['downstream'] for v in trace['rows']])))<1e-12 and np.max(abs(up))<1e-12)
    checks[f'orientations_{n}']=bool(np.max(np.linalg.norm(Q.transpose(0,2,1)@Q-np.eye(3),axis=(1,2)))<1e-10)
    checks[f'full_exit_{n}']=bool(p[-1,0]-h[-1]>=4)
    maxmass=max(maxmass,float(np.max(abs(up+inside+down-1))));minimum=min(minimum,float(np.min(np.linalg.norm(p,axis=1)-1-.2)))
    histories[n]=(p,Q,times,down)
checks['balance']=maxmass<1e-12;checks['clearance_snapshot']=minimum>.05
checks['artifact_hashes']=all(hashlib.sha256((run/k).read_bytes()).hexdigest()==v for k,v in r['artifacts'].items())
(out/'results.json').write_text(json.dumps({'checks':checks,'passed':all(checks.values()),'max_mass_residual':maxmass,'minimum_bounding_sphere_gap_snapshots':minimum,'python':platform.python_version(),'run_hash':hashlib.sha256((root/'evaluation_01/results.json').read_bytes()).hexdigest()},indent=2))
if not all(checks.values()):raise ValueError('audit failed')
p,Q,t,d=histories[48];fig,ax=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
ax[0].add_patch(plt.Circle((0,0),1,color='.4'));ax[0].plot(p[:,0],p[:,1],color='#257e97');theta=np.linspace(0,2*np.pi,100)
for j in np.linspace(0,len(p)-1,7,dtype=int):
    edge=p[j]+np.cos(theta)[:,None]*.2*Q[j,:,0]+np.sin(theta)[:,None]*.1*Q[j,:,1]
    ax[0].plot(edge[:,0],edge[:,1],color='#257e97',lw=.8)
ax[0].axvline(4,color='#b14335',ls='--');ax[0].set(aspect='equal',xlim=(-3.5,4.8),ylim=(-1.3,3.2),xlabel='x / grain radius',ylabel='y / grain radius',title='Finite prolate path and equator projections')
for n in [12,24,48]:
    _,_,ts,ds=histories[n];ax[1].plot(ts,ds,marker='.',label=f'{n} nominal steps')
ax[1].set(xlabel='Time / (grain radius / far-field speed)',ylabel='Tagged body mass beyond outlet',ylim=(-.03,1.03),title='Single body: complete passage, not a population rate');ax[1].legend();ax[1].grid(alpha=.2)
fig.suptitle('Finite-body outlet pilot — one fixed grain, no contact or soil validation',fontsize=12)
fig.savefig(out/'finite_release.png',dpi=160);plt.close(fig)
print(checks)
