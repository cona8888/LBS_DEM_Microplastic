"""Compare streaming metrics against original whole-time-vector and scalar oracles."""
from pathlib import Path
import sys,time
import numpy as np
import streaming_path_metrics_v1 as candidate
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage177_staging'))
import audit_extended_preflight_v1 as previous
api=previous.api
DESIGN=ROOT/'stage180_designs/incremental_audit_20260924/metric_design_01.json'
OUT=ROOT/'stage180_evaluations/incremental_audit_20260924/metrics_01'
KEYS=['whole_position_over_b_max','whole_axis_vector_norm_max','endpoint_q_over_U_max','mean_L1_q_over_U_max','integrated_q_error_over_U_s','interval_velocity_sup_over_U_diagnostic_only']


def prepare():
    d={'stage':'Stage180 streaming metric units','new_trajectory_steps':0,'physical_changes':[],
       'seeds':list(range(18000,18024)),'sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,candidate.__file__,previous.stream_audit.__file__]},
       'limits':'Original gates remain outside this calculator; oracle agreement rtol=2e-13, atol=2e-14 on synthetic dimensionless cases.',
       'cases':'Random unequal grids/endpoints, irregular block sizes, analytical interval tests, invalid-input rejection.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def blocks(arr,sizes):
    i=1;k=0
    while i<len(arr):
        n=sizes[k%len(sizes)];yield arr[i:i+n];i+=n;k+=1


def scalar_l1(a,b):
    i=j=1;t=0.;total=0.;stop=min(a[-1,0],b[-1,0])
    while t<stop:
        nxt=min(a[i,0],b[j,0],stop);total+=(nxt-t)*np.linalg.norm(a[i,7:13]-b[j,7:13]);t=nxt
        if a[i,0]==t:i+=1
        if b[j,0]==t:j+=1
    return total/stop


def run():
    d=api.read(DESIGN);api.verify_mapping(d['sources']);OUT.mkdir(exist_ok=False,parents=True);checks=[];start=time.perf_counter()
    for seed in d['seeds']:
        rng=np.random.default_rng(seed)
        def trace(n,end):
            x=rng.normal(size=(n+1,13));x[:,0]=np.r_[0.,np.sort(rng.uniform(1e-7,end-1e-7,n-1)),end];return x
        a=trace(int(rng.integers(2,300)),float(rng.uniform(.2,1.)));b=trace(int(rng.integers(2,300)),float(rng.uniform(.2,1.)))
        reference=previous.stream_audit.metrics(a,b,1.,1.,chunk=23)
        for sa,sb in [([1],[1]),([3,19,2],[8,1,31]),([1000],[1000])]:
            got=candidate.metrics(blocks(a,sa),blocks(b,sb),a[0],b[0],a[-1,0],b[-1,0],1.,1.)
            api.require(all(np.isclose(got[k],reference[k],rtol=2e-13,atol=2e-14) for k in KEYS),'whole-vector oracle agreement')
            api.require(np.isclose(got['mean_L1_q_over_U_max'],scalar_l1(a,b),rtol=2e-13,atol=2e-14),'independent scalar L1')
            checks.append({'seed':seed,'block_sizes':[sa,sb],'passed':True,'working_set':got['working_set']})
        identical=candidate.metrics(blocks(a,[1,7]),blocks(a,[13]),a[0],a[0],a[-1,0],a[-1,0],1.,1.)
        api.require(all(identical[k]==0. for k in KEYS),'identity across block boundaries')
    a=np.zeros((3,13));b=np.zeros((3,13));a[:,0]=[0.,.25,.75];b[:,0]=[0.,.5,1.];a[1:,7]=2.;b[1:,7]=1.
    analytical=candidate.metrics(blocks(a,[1]),blocks(b,[1]),a[0],b[0],.75,1.,1.,1.)
    api.require(analytical['common_stop_s']==.75 and analytical['mean_L1_q_over_U_max']==1. and analytical['endpoint_q_over_U_max']==1.,'unequal-end exact oracle')
    shifted_a=a.copy();shifted_b=b.copy();shifted_a[:,0]+=10.;shifted_b[:,0]+=10.
    shifted=candidate.metrics(blocks(shifted_a,[1]),blocks(shifted_b,[1]),shifted_a[0],shifted_b[0],10.75,11.,1.,1.)
    api.require(shifted['common_duration_s']==.75 and shifted['mean_L1_q_over_U_max']==1.,'nonzero conditional clock')
    guards=[]
    def reject(label,fn):
        try:fn()
        except ValueError:guards.append(label);return
        raise AssertionError('guard accepted '+label)
    reject('missing_block',lambda:candidate.metrics(iter([a[1:2]]),blocks(b,[1]),a[0],b[0],.75,1.,1.,1.))
    reject('duplicate_clock',lambda:candidate.metrics(iter([np.vstack([a[1],a[1]])]),blocks(b,[1]),a[0],b[0],.75,1.,1.,1.))
    reject('empty_block',lambda:candidate.metrics(iter([np.empty((0,13))]),blocks(b,[1]),a[0],b[0],.75,1.,1.,1.))
    reject('wrong_shape',lambda:candidate.metrics(iter([np.ones((1,12))]),blocks(b,[1]),a[0],b[0],.75,1.,1.,1.))
    reject('nan_node',lambda:candidate.metrics(iter([np.full((1,13),np.nan)]),blocks(b,[1]),a[0],b[0],.75,1.,1.,1.))
    reject('zero_speed',lambda:candidate.metrics(blocks(a,[1]),blocks(b,[1]),a[0],b[0],.75,1.,1.,0.))
    reject('wrong_endpoint',lambda:candidate.metrics(blocks(a,[1]),blocks(b,[1]),a[0],b[0],.7,1.,1.,1.))
    report={'passed':True,'oracle_cases':checks,'identity_cases':len(d['seeds']),'analytical':analytical,'conditional_clock':shifted,'guard_rejections':guards,
            'new_trajectory_steps':0,'wall_s':time.perf_counter()-start,'design_sha256':api.sha(DESIGN),'production_ready':False,
            'claim':'Calculator qualification only. A complete independently audited raw manifest is still required.'}
    api.verify_mapping(d['sources']);api.write(OUT/'results.json',report);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('METRICS_PASS',len(checks),'GUARDS',len(guards),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
