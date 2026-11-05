#!/usr/bin/env python3
"""Reproduce the bounded dry-contact review; no experimental parameter fitting.
Works inside both the full RhizoField source and the published standalone module.
Python dependency: NumPy. C++17 compiler and make must be installed.
"""
from pathlib import Path
import argparse, csv, hashlib, json, os, platform, subprocess, time
import numpy as np
HERE=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'review_run')
    parser.add_argument('--timing-repeats',type=int,default=5)
    parser.add_argument('--resume',action='store_true',help='reuse this revision’s completed case checkpoint; still rerun tests and timings')
    args=parser.parse_args()
    if args.timing_repeats<1:parser.error('timing-repeats must be positive')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    with (out/'build_and_tests.log').open('w') as log:
        subprocess.run(['make','test','bin/integration_test','bin/growth_cell','bin/native_probe'],cwd=HERE,stdout=log,stderr=subprocess.STDOUT,check=True,env=env)
        subprocess.run([str(HERE/'bin/integration_test'),str(out)],stdout=log,stderr=subprocess.STDOUT,check=True,env=env)
    for axis in ('tip','radial'):
        with (out/f'probe_{axis}.csv').open('w') as f:
            subprocess.run([str(HERE/'bin/native_probe'),axis,'cached','6000'],stdout=f,stderr=subprocess.PIPE,check=True,env=env)
    source_files=[p for p in HERE.rglob('*') if p.is_file() and (p.suffix in ('.hpp','.cpp') or p.name=='Makefile') and 'bin' not in p.parts]
    fingerprint={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    checkpoint=out/'case_checkpoint.json'
    if args.resume:
        saved=json.loads(checkpoint.read_text())
        if saved['source_sha256']!=fingerprint:raise RuntimeError('source changed since case checkpoint')
        for name,digest in saved['output_sha256'].items():
            if hashlib.sha256((out/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('case output changed: '+name)
    rows=[]
    configs=[('symmetric',n,mode,1,.0001) for n in (4000,8000,16000,32000,64000) for mode in ('direct','cached')]
    configs += [('held',n,'cached',1,.0001) for n in (8000,32000)]
    configs += [('symmetric',16000,'cached',s,.0001) for s in (2,4)]
    configs += [('symmetric',8000,'cached',1,0.)]
    def execute(method,n,mode,sub=1,travel=.0001,path=None):
        command=[str(HERE/'bin/growth_cell'),mode,str(n),str(sub),str(travel),method]
        start=time.perf_counter()
        with (path.open('w') if path else open(os.devnull,'w')) as f:
            subprocess.run(command,stdout=f,stderr=subprocess.PIPE,check=True,env=env,timeout=180)
        return time.perf_counter()-start
    if args.resume:
        rows=list(csv.DictReader((out/'growth_summary.csv').open()))
    else:
        for method,n,mode,sub,travel in configs:
            tag=f'{method}_{mode}_n{n}_sub{sub}_'+('static' if travel==0 else 'grow')
            elapsed=execute(method,n,mode,sub,travel,out/(tag+'.csv'))
            a=np.genfromtxt(out/(tag+'.csv'),delimiter=',',names=True)
            row=dict(case=tag,method=method,mode=mode,steps=n,dt_s=.04/n,subdivisions=sub,tip_advance_m=travel,elapsed_s=elapsed,
              sampled_peak_force_N_per_m=float(np.max(a['grain_root_reaction_N_per_m'])),peak_force_N_per_m=float(a['running_peak_force_N_per_m'][-1]),final_max_grain_motion_m=float(a['max_grain_motion_m'][-1]),
              max_root_overlap_m=float(np.max(a['max_root_overlap_m'])),root_work_J_per_m=float(a['root_actuation_work_J_per_m'][-1]),
              accumulated_kick_work_residual_J_per_m=float(a['kick_work_residual_J_per_m'][-1]))
            rows.append(row);print(tag,'peak=',row['peak_force_N_per_m'],flush=True)
    def read(tag):return np.genfromtxt(out/(tag+'.csv'),delimiter=',',names=True)
    ref=read('symmetric_cached_n64000_sub1_grow');force='grain_root_reaction_N_per_m';den=ref['running_peak_force_N_per_m'][-1];checks={}
    for row in rows:
        a=read(row['case'])
        row['max_force_curve_error_vs_64000']=float(np.max(np.abs(a[force]-ref[force]))/den)
    for n in (4000,8000,16000,32000,64000):
        d=read(f'symmetric_direct_n{n}_sub1_grow');c=read(f'symmetric_cached_n{n}_sub1_grow')
        checks[f'direct_cached_{n}']=max(float(np.max(np.abs(d[k]-c[k]))) for k in d.dtype.names)
    for sub in (2,4):
        a=read(f'symmetric_cached_n16000_sub{sub}_grow');b=read('symmetric_cached_n16000_sub1_grow')
        checks[f'segmentation_{sub}_force_relative']=float(np.max(np.abs(a[force]-b[force]))/b[force].max())
    checks['finest_pair_max_force_curve_relative']=next(r['max_force_curve_error_vs_64000'] for r in rows if r['case']=='symmetric_cached_n32000_sub1_grow')
    fine=read('symmetric_cached_n32000_sub1_grow')
    checks['finest_pair_peak_relative']=abs(float(fine['running_peak_force_N_per_m'][-1]/den-1))
    checks['finest_pair_force_envelope_relative']=max(float(abs(fine[k]-ref[k]).max()/den) for k in ('interval_min_force_N_per_m','interval_max_force_N_per_m'))
    static=read('symmetric_cached_n8000_sub1_static')
    checks['static_max_motion_m']=float(static['max_grain_motion_m'].max());checks['static_max_force_N_per_m']=float(abs(static[force]).max())
    with (out/'growth_summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    checkpoint.write_text(json.dumps(dict(source_sha256=fingerprint,
        output_sha256={r['case']+'.csv':hashlib.sha256((out/(r['case']+'.csv')).read_bytes()).hexdigest() for r in rows}),indent=2)+'\n')
    # Interleaved identical-physics whole-driver timings, including startup/output.
    timing=[];choices=[('symmetric','cached'),('symmetric','direct'),('held','cached')]
    for rep in range(args.timing_repeats):
        for offset in range(len(choices)):
            method,mode=choices[(rep+offset)%len(choices)]
            timing.append(dict(repetition=rep,method=method,mode=mode,steps=16000,elapsed_s=execute(method,16000,mode)))
    with (out/'whole_driver_timing.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(timing[0]));w.writeheader();w.writerows(timing)
    checks['status']='PASS' if (max(v for k,v in checks.items() if k.startswith('direct_cached'))<1e-12 and checks['finest_pair_max_force_curve_relative']<.02 and checks['finest_pair_peak_relative']<.01 and checks['finest_pair_force_envelope_relative']<.02 and max(v for k,v in checks.items() if k.startswith('segmentation'))<.001 and checks['static_max_motion_m']<1e-12 and checks['static_max_force_N_per_m']<1e-12) else 'FAIL'
    (out/'growth_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    sources={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.rglob('*') if p.is_file() and (p.suffix in ('.hpp','.cpp') or p.name in ('Makefile','run_review.py')) and 'bin' not in p.parts}
    info=dict(python=platform.python_version(),numpy=np.__version__,system=platform.platform(),compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],source_sha256=sources,environment={k:env[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')})
    (out/'run_manifest.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(checks,indent=2));assert checks['status']=='PASS'
if __name__=='__main__':main()
