"""Tiny exact inner-optimizer replay; zero integration and no runtime patches.

This checks the isolated getter idea before investing in a full force-route
qualification. Its fixed seeds/poses are development probes, not trajectories
or a distribution of production cost. Preserve any negative timing/evidence.
"""
from datetime import datetime, timezone
from pathlib import Path
import os, sys, time, traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage199_staging'),str(ROOT/'stage196_staging'),str(ROOT/'stage194_staging')]
import numpy as np
import psutil
import native_trust_candidate_v4 as live
import check_split_pair_v1 as point
candidate = point.candidate
OUT = point.OUT.with_name('inner_optimizer_01')
DESIGN = point.DESIGN.with_name('inner_optimizer_01.json')


def inventory():
    payload = point.authenticate()
    rows = []
    fields = ('vfree','mobility','jacobian','gaps_m','dt_s','friction')
    for name in ('early_attempts','fallback_systems'):
        data = payload[name]
        available = [i for i,r in enumerate(data) if all(k in r for k in fields)]
        for j in np.linspace(0,len(available)-1,8,dtype=int):
            index=available[int(j)];row=data[index]
            # Same canonical ordering as the Stage194 semismooth source.
            v,M,J,g=[np.asarray(row[k],float) for k in fields[:4]]
            order=sorted(range(3),key=lambda k:(float(g[k]),*J[3*k:3*k+3].ravel().tolist()))
            idx=[3*k+j for k in order for j in range(3)]
            seed=row.get('health',{}).get('seed_reactions')
            rows.append(dict(label=f'{name}_{index}',subset=name,
                             vfree=v.tolist(),mobility=M.tolist(),jacobian=J[idx].tolist(),
                             gaps_m=g[order].tolist(),dt_s=row['dt_s'],friction=row['friction'],
                             seed_force=None if seed is None else np.asarray(seed)[idx].tolist(),
                             seed_kind='captured_same_system' if seed is not None else 'zero_development_probe'))
    return rows


def prepare():
    assert time.time()<point.DEADLINE
    prior=point.read(point.OUT/'results.json')
    assert prior['passed'] and point.read(point.OUT/'completion.json')['results_sha256']==point.sha(point.OUT/'results.json')
    point.commit(OUT/'fixtures.json',inventory())
    sources=[Path(__file__).resolve(),Path(point.__file__),Path(candidate.__file__),Path(candidate.previous.__file__),
             Path(live.__file__),Path(live.previous.__file__),Path(live.prior.__file__),
             ROOT/'stage199_staging/exact_trf_helpers_v1.py',ROOT/'stage198_staging/direct_trf_v1.py']
    inputs=[OUT/'fixtures.json',point.OUT/'results.json',point.OUT/'completion.json',point.DESIGN,
            point.FOLDER/'results.json',point.FOLDER/'call.json.xz',point.FOLDER/'call.json.seal.json']
    point.commit(DESIGN,dict(stage='Stage224 tiny split-callback inner-optimizer screen',
                            sources={str(p):point.sha(p) for p in sources},inputs={str(p):point.sha(p) for p in inputs},
                            new_trajectory_steps=0,maximum_optimizer_calls=64,maximum_wall_seconds=45,
                            baseline='Current native trust v4 with unchanged TRF body and eager compiled analytic pair',
                            modes=['baseline','split'],repeats=2,logical_cpu=14,
                            deadline_utc='2026-10-07T12:10:57+00:00',
                            unchanged_controls=dict(method='trf',xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=2000,x_scale='jac'),
                            criteria='Exact optimizer result bytes and iteration/status fields. Timing is provisional, not full-route cost.',
                            production_authorized=False,physical_route_qualified=False))
    print('PREPARED_OPTIMIZER',16,'poses, <=64 optimizer calls, zero trajectory steps')


def fingerprint(result):
    return {k:(np.asarray(result[k]).shape,np.asarray(result[k]).dtype.str,np.asarray(result[k]).tobytes())
            for k in ('x','fun','jac','grad','cost','optimality','nfev','njev','status','success')}


def run():
    design=point.read(DESIGN)
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'))
    for path,digest in {**design['sources'],**design['inputs']}.items():assert point.sha(path)==digest,path
    assert time.time()<point.DEADLINE
    psutil.Process().cpu_affinity([design['logical_cpu']])
    point.commit(OUT/'launch.json',dict(pid=os.getpid(),created=psutil.Process().create_time(),argv=sys.argv,
                                     utc=datetime.now(timezone.utc).isoformat(),design_sha256=point.sha(DESIGN),new_trajectory_steps=0))
    start=time.monotonic();reports=[];calls=0
    try:
        # Exclude compilation/import from measured paired solve time. Both
        # kernels were compiled in the earlier arithmetic screening.
        for V in (np.eye(9),np.asfortranarray(np.eye(9))):
            for alpha in (None,0.,.03):
                live.trust(9,9,np.ones(9),np.arange(1.,10.),V,.1,initial_alpha=alpha)
        for index,row in enumerate(point.read(OUT/'fixtures.json')):
            args=tuple(np.array(row[k],float) for k in ('vfree','mobility','jacobian','gaps_m'))+(row['dt_s'],row['friction'])
            signature=None;timings={'baseline':[],'split':[]};counts={}
            for repeat in range(design['repeats']):
                order=design['modes'] if (index+repeat)%2==0 else list(reversed(design['modes']))
                for mode in order:
                    assert time.monotonic()-start<design['maximum_wall_seconds'] and time.time()<point.DEADLINE
                    assert calls<design['maximum_optimizer_calls'];calls+=1
                    pair,*constants=(candidate.previous if mode=='baseline' else candidate).optimized_system(*args)
                    scales,vs=constants[-2:]
                    seed=np.zeros(9) if row['seed_force'] is None else np.array(row['seed_force'])*scales/vs
                    f=(lambda y:pair(y)[0]) if mode=='baseline' else pair.residual
                    j=(lambda y:pair(y)[1]) if mode=='baseline' else pair.derivative
                    def bounded_f(y):
                        if time.monotonic()-start>=design['maximum_wall_seconds'] or time.time()>=point.DEADLINE:
                            raise RuntimeError('bounded optimizer screen cutoff')
                        return f(y)
                    tick=time.perf_counter()
                    result=live.least_squares(bounded_f,seed,jac=j,**design['unchanged_controls'])
                    timings[mode].append(time.perf_counter()-tick)
                    got=fingerprint(result)
                    if signature is None:signature=got
                    assert got==signature,'Exact optimizer result '+row['label']+' '+mode
                    counts[mode]=dict(nfev=int(result.nfev),njev=int(result.njev),status=int(result.status))
            reports.append(dict(label=row['label'],subset=row['subset'],seed_kind=row['seed_kind'],
                                exact_optimizer=True,timings=timings,counts=counts))
        for path,digest in {**design['sources'],**design['inputs']}.items():assert point.sha(path)==digest,path
        summary={}
        for subset in ('early_attempts','fallback_systems'):
            selected=[r for r in reports if r['subset']==subset]
            totals={mode:sum(sum(r['timings'][mode]) for r in selected) for mode in design['modes']}
            summary[subset]=dict(totals=totals,provisional_inner_speedup=totals['baseline']/totals['split'])
        result=dict(passed=True,utc=datetime.now(timezone.utc).isoformat(),design_sha256=point.sha(DESIGN),
                    optimizer_calls=calls,new_trajectory_steps=0,elapsed_seconds=time.monotonic()-start,
                    summaries=summary,reports=reports,production_authorized=False,
                    physical_route_qualified=False,restart_qualified=False,full_path_qualified=False,
                    claim='Tiny development-seed inner-optimizer comparison only. Timing includes no outer force-selection/physical-audit costs and is not a production speedup. Zero-seed fallback probes are not replays of their recorded projection branch.')
        point.commit(OUT/'results.json',result)
        point.commit(OUT/'completion.json',dict(passed=True,results_sha256=point.sha(OUT/'results.json')))
        print('INNER_EXACT',calls,summary)
    except Exception as error:
        point.commit(OUT/'failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),
                                          completed=reports,optimizer_calls=calls,new_trajectory_steps=0))
        raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
