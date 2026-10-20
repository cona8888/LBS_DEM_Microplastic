"""Bounded same-input primary/fallback diagnosis; never advances a trajectory."""
from pathlib import Path
from types import FunctionType, SimpleNamespace
from datetime import datetime, timezone
import ast
import copy
import inspect
import json
import os
import subprocess
import sys
import time
import traceback
import numpy as np
import psutil

sys.path.insert(0,str(Path(__file__).resolve().parent))
import reconstruct_fixed_pose_v3 as reconstruction
s=reconstruction.s; core=s.q.guard.core
BASE=s.ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015/fixed_systems_02'
PREVIOUS=BASE.with_name('fixed_systems_01')
DESIGN=BASE/'design_01.json'
END='2026-10-15T08:03:49.377827+00:00'


def plain(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,(list,tuple)):return [plain(x) for x in value]
    if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
    return value


def bound():
    s.environment();s.require(datetime.now(timezone.utc)<datetime.fromisoformat(END),'Existing analysis cutoff')
    s.require(__import__('shutil').disk_usage(s.ROOT).free>20*1024**3,'Unchanged disk reserve')
    s.require(sum(p.stat().st_size for p in BASE.rglob('*') if p.is_file())<32*1024**2,'32MiB diagnostic ceiling')


def capture_inner(data):
    args=copy.deepcopy(data['outer_arguments']);args[:6]=[np.asarray(x,float) for x in args[:6]]
    args[6]=[(int(k),float(g),np.asarray(n,float),np.asarray(l,float)) for k,g,n,l in args[6]]
    original=core.prior.JOB.observer.backend.stage42.inertial_contact_step;records=[]
    class Captured(Exception):pass
    def intercept(v,M,J,g,dt,mu,tol,maxiter):
        records.append([v,M,J,g,dt,mu,tol,maxiter]);raise Captured()
    proxy=SimpleNamespace(**{**vars(original.__globals__['stage41']),'_solve_prepared':intercept})
    fn=FunctionType(original.__code__,{**original.__globals__,'stage41':proxy},original.__name__,original.__defaults__,original.__closure__)
    try:fn(*args)
    except Captured:pass
    s.require(len(records)==1 and fn.__code__ is original.__code__,'Original first physical map, intercepted before solve')
    values=records[0]
    s.require(core.digest_args(values)==data['expected_first_inner']['input_sha256'],'Every original first-map input matches archived bytes')
    return plain(values)


def prepare():
    bound();s.require(not BASE.exists(),'Create-only diagnostic repair')
    old=s.read(PREVIOUS/'design_01.json');negative=s.fields.sealed(PREVIOUS/'final_01/results.json')
    s.require(not negative['passed'] and negative['attempted_contact_calls']==1
        and negative['completed_contact_calls']==0 and negative['new_transport_steps']==0,'Preserve original startup negative')
    s.api.verify_mapping(old['source_files']);s.api.verify_mapping(old['inputs']);s.api.verify_mapping(negative['artifacts'])
    launch=s.read(PREVIOUS/'call_00_primary/launch.json');s.require(s.identity(launch)['retired'],'Exact old diagnostic process retired')
    rows=[];inputs=dict(old['inputs']);BASE.mkdir(parents=True,exist_ok=False)
    # No native solver outcome was observed in attempt01. Omit one redundant
    # transition sample prospectively, retaining both endpoint samples and
    # charging the previous failed worker reservation conservatively.
    for index,original_index in enumerate((0,1,2,4,5)):
        original=old['fixtures'][original_index];s.require(s.sha(original['path'])==original['sha256'],'Exact earlier reconstructed fixture')
        data=s.read(original['path']);data['archived_fixture_id']=original_index;data['fixture_id']=index
        path=BASE/f'fixture_{index:02d}.json';s.commit(path,data)
        rows.append(dict(path=str(path),sha256=s.sha(path),contacts=original['contacts'],fixture_id=index))
        inputs[original['path']]=original['sha256']
    for path in (PREVIOUS/'design_01.json',PREVIOUS/'final_01/results.json',PREVIOUS/'final_01/completion.json'):
        inputs[str(path)]=s.sha(path)
    sources={**old['source_files'],str(Path(__file__).resolve()):s.sha(Path(__file__))}
    s.commit(DESIGN,dict(passed=True,fixtures=rows,inputs=inputs,source_files=sources,end_utc=END,
        maximum_contact_calls=10,prior_worker_reservations_retained=1,shared_maximum_contact_reservations=12,
        previous_unqualified_contact_reservation_preserved=True,maximum_seconds_per_worker=45,
        maximum_output_bytes=32*1024**2,workers=1,threads=1,logical_cpu=14,new_transport_steps=0,
        production_authorized=False,physical_equation_changes=[],accuracy_gate_changes=[],
        warmup='Original immutable arithmetic templates;0 contact/optimizer calls, before started marker.',
        context=old['context'],selection='Five predeclared saved poses from original six, before native outcome observations; no representative campaign inference.',utc=s.utc()))
    print('SAME_INPUT_FIXTURE_REPAIR_PREPARED',s.sha(DESIGN),len(rows),flush=True)


def zero_lm():
    original=core.prior.kernel.ORIGINAL_ZERO
    tree=ast.parse(inspect.getsource(original));fn=tree.body[0]
    s.require(isinstance(fn.body[0],ast.Try),'Original primary-first zero-LM structure')
    fn.body=fn.body[1:];fn.name='counterfactual_original_zero_lm'
    ast.fix_missing_locations(tree);namespace=dict(original.__globals__)
    exec(compile(tree,str(Path(__file__).resolve())+'::original_zero_lm_suffix_only','exec'),namespace)
    return namespace[fn.name]


def worker(fixture_id,mode):
    bound();psutil.Process().cpu_affinity([14]);d=s.read(DESIGN)
    s.api.verify_mapping(d['source_files']);s.api.verify_mapping(d['inputs'])
    row=d['fixtures'][fixture_id];s.require(s.sha(row['path'])==row['sha256'],'Immutable input fixture')
    data=s.read(row['path']);values=data['inner_arguments'];args=[np.asarray(v,float) for v in values[:4]]+values[4:]
    folder=BASE/f'call_{fixture_id:02d}_{mode}';before=core.digest_args(args)
    s.require(before==data['expected_first_inner']['input_sha256'],'Same complete physical input')
    warm=core.prior.kernel.warm();s.require(warm['passed'] and warm['contact_solver_calls']==warm['outer_calls']==0,'Original arithmetic-only warmup')
    s.commit(folder/'warmup.json',warm)
    s.commit(folder/'started.json',dict(input_sha256=before,contact_calls_attempted=1,new_transport_steps=0,utc=s.utc()))
    tick=time.perf_counter()
    with core.direct_scope(False,datetime.fromisoformat(END).timestamp()) as primary:
        answer=primary(*args) if mode=='primary' else zero_lm()(*args)
        physics=core.physical_output(args,answer)
    s.require(core.digest_args(args)==before,'No physical input mutation')
    expected=np.asarray(data['expected_first_inner']['map_output'],float)
    archive_bits=np.asarray(answer[0],float).tobytes()==expected.tobytes()
    if mode=='primary':s.require(archive_bits,'Original primary reproduces archived first map exactly')
    s.seal(folder,dict(passed=True,input_sha256=before,contact_calls_attempted=1,new_transport_steps=0,
        mode=mode,answer=plain(answer),independent_physics=plain(physics),primary_archive_bits=archive_bits,
        force_call_seconds=time.perf_counter()-tick,production_authorized=False,utc=s.utc()))


def run():
    bound();d=s.read(DESIGN);calls=0;reports=[];error=None
    try:
        for row in d['fixtures']:
            pair={}
            for mode in ('primary','fallback'):
                if mode=='fallback' and row['contacts']==0:continue
                bound();s.require(calls<d['maximum_contact_calls'] and calls+1+d['prior_worker_reservations_retained']<=d['shared_maximum_contact_reservations'],'Shared original nonadvancing reservation ceiling');calls+=1
                folder=BASE/f"call_{row['fixture_id']:02d}_{mode}";folder.mkdir(exist_ok=False)
                command=[str(s.PYTHON),'-B','-u',str(Path(__file__).resolve()),'worker',str(row['fixture_id']),mode]
                with (folder/'stdout.log').open('xb') as out,(folder/'stderr.log').open('xb') as err:
                    proc=subprocess.Popen(command,cwd=s.ROOT,env=os.environ.copy(),stdout=out,stderr=err,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    launch=dict(pid=proc.pid,created=psutil.Process(proc.pid).create_time(),command=command)
                    s.commit(folder/'launch.json',launch)
                    try:code=proc.wait(timeout=min(45,max(.1,datetime.fromisoformat(END).timestamp()-time.time())))
                    except subprocess.TimeoutExpired:
                        s.stop_owned(proc,launch);raise RuntimeError('Exact diagnostic child exceeded frozen wall cap')
                s.require(s.identity(launch)['retired'],'Exact diagnostic child retired')
                s.commit(folder/'exit.json',dict(returncode=code,launch_sha256=s.sha(folder/'launch.json'),
                    logs={str(p):s.sha(p) for p in folder.glob('*.log')},utc=s.utc()))
                s.require(code==0,'Diagnostic negative retained; stop dependent probes')
                pair[mode]=s.fields.sealed(folder/'results.json')
            difference=None
            if 'fallback' in pair:
                speed=s.read(row['path'])['speed_m_s']
                difference=float(np.linalg.norm(np.asarray(pair['primary']['answer'][0])-np.asarray(pair['fallback']['answer'][0]))/speed)
            reports.append(dict(fixture_id=row['fixture_id'],contacts=row['contacts'],difference_over_U=difference,
                                primary_archive_bits=pair['primary']['primary_archive_bits']))
            print('SAME_SYSTEM_PAIR',row['fixture_id'],difference,flush=True)
    except Exception as issue:
        error=dict(message=repr(issue),traceback=traceback.format_exc());raise
    finally:
        artifacts={str(p):s.sha(p) for p in BASE.rglob('*') if p.is_file() and 'final_01' not in p.parts}
        completed=sum((BASE/f"call_{row['fixture_id']:02d}_{mode}/completion.json").exists()
                      for row in d['fixtures'] for mode in ('primary','fallback'))
        s.seal(BASE/'final_01',dict(passed=error is None,error=error,attempted_contact_calls=calls,
            completed_contact_calls=completed,unknown_or_unqualified_contact_calls=calls-completed,
            new_transport_steps=0,unknown_transport_steps=0,reports=reports,artifacts=artifacts,
            prior_unqualified_worker_reservations_preserved=1,total_shared_contact_reservations=1+calls,
            production_authorized=False,original_accuracy_gates_changed=False,utc=s.utc()))


if __name__=='__main__':
    if sys.argv[1]=='worker':worker(int(sys.argv[2]),sys.argv[3])
    else:{'prepare':prepare,'run':run}[sys.argv[1]]()
