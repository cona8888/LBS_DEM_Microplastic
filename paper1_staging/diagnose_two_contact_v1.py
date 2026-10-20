"""Prepared identical-input probes of the newly localized two-contact episode.

Preparation reconstructs operands only. Native solves require a separately
sealed human approval; no transport or production installation is provided.
"""
from pathlib import Path
from types import FunctionType
from datetime import datetime, timezone, timedelta
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnose_fixed_system_v2 as old
s = old.s
SELF = Path(__file__).resolve()
DESIGNS = s.ROOT/'paper1_designs/two_contact_onset_20261015'
PROPOSAL = DESIGNS/'proposal_01.json'
DESIGN = DESIGNS/'design_01.json'
BASE = s.ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015/two_contact_systems_01'


def prepare():
    s.environment()
    assert not PROPOSAL.exists() and not DESIGN.exists() and not BASE.exists()
    prior = s.fields.sealed(old.BASE/'final_01/results.json')
    assert prior['passed'] and prior['total_shared_contact_reservations'] == 11
    s.api.verify_mapping(prior['artifacts'])
    analysis = s.ROOT/'paper1_evaluations/fibre_accuracy_diagnosis_20261015/early_divergence_01/results.json'
    a = s.fields.sealed(analysis); assert a['passed'] and a['new_contact_solver_calls'] == 0
    s.api.verify_mapping(a['inputs']); s.api.verify_mapping(a['source_files'])
    local = s.ROOT/'paper1_runs/local_common_state_20261015/interpretation_01/results.json'
    assert s.fields.sealed(local)['passed']
    fixtures = []; inputs = {str(analysis):s.sha(analysis), str(local):s.sha(local), str(old.BASE/'final_01/results.json'):s.sha(old.BASE/'final_01/results.json')}
    for name, label, index, target in [
        ('p1_i0_fibre_u0p5_fine_20261014', 'production_00074', 4124, None),
        ('p1_i0_fibre_u0p5_fine_20261014', 'production_00075', None, .231),
        ('p1_i0_fibre_u0p5_accuracy_recovery_20261014', 'production_00148', 3250, None),
        ('p1_i0_fibre_u0p5_accuracy_recovery_20261014', 'production_00149', None, .231)]:
        trace = s.ROOT/'paper1_runs'/name/'records'/label/'trace.npy'
        rows = np.load(trace, mmap_mode='r', allow_pickle=False)
        if target is not None:
            index = int(np.searchsorted(rows[:, 0], target))
        data = old.reconstruction.inspect_one(name, label, index, include_fixture=True)
        assert data['report']['dt_exact'] and data['report']['contacts_exact']
        assert len(data['outer_arguments'][6]) == 2
        assert sorted(c[0] for c in data['outer_arguments'][6]) == [15, 182]
        data['inner_arguments'] = old.capture_inner(data)
        assert old.core.digest_args([np.asarray(v, float) for v in data['inner_arguments'][:4]] + data['inner_arguments'][4:]) == data['expected_first_inner']['input_sha256']
        data['fixture_id'] = len(fixtures); data['saved_row_time_s'] = float(rows[index, 0])
        path = DESIGNS/f'fixture_{len(fixtures):02d}.json'; s.commit(path, data)
        J = np.asarray(data['inner_arguments'][2]); M = np.asarray(data['inner_arguments'][1])
        eig = np.linalg.eigvalsh(J@M@J.T)
        normal = J[::3]@M@J[::3].T
        fixtures.append(dict(path=str(path),sha256=s.sha(path),fixture_id=data['fixture_id'],contacts=2,
            source_root=name,label=label,index=index,saved_row_time_s=data['saved_row_time_s'],
            full_delassus_eigenvalues=eig.tolist(),normal_delassus_eigenvalues=np.linalg.eigvalsh(normal).tolist()))
        inputs.update(data['inputs']);inputs[str(path)]=s.sha(path)
    prior_design = s.read(old.DESIGN)
    sources = {**prior_design['source_files'],str(SELF):s.sha(SELF),str(Path(old.__file__).resolve()):s.sha(old.__file__)}
    s.api.verify_mapping(sources);s.api.verify_mapping(inputs)
    s.commit(PROPOSAL,dict(passed=True,status='REQUIRES_SEPARATE_HUMAN_APPROVAL',dispatch_authorized=False,
        question='Do original primary and fallback routes agree on identical two-contact systems in the first non-halving episode?',
        fixtures=fixtures,source_files=sources,inputs=inputs,maximum_contact_calls=8,maximum_window_minutes=15,
        prior_nonadvancing_contact_reservations=11,maximum_shared_nonadvancing_contact_reservations_after=19,
        maximum_seconds_per_worker=45,workers=1,threads=1,logical_cpu=14,maximum_output_bytes=32*1024**2,
        maximum_total_paper1_bytes=20*1024**3,
        minimum_free_disk_bytes=20*1024**3,new_transport_steps=0,maximum_new_saved_steps=0,
        original_physics_and_accuracy_gates_unchanged=True,production_authorized=False,successor_dispatch_authorized=False,
        selection='Two archived dt levels; first both-bearing contact15/182 pose and first saved pose at or after0.231s at each level.',
        controls=dict(exact_original_assembly_and_saved_dt=True,full_first_inner_input_hashes=True,
            original_worker_bytecode_reused=True,no_solver_called_during_preparation=True),utc=s.utc()))
    print('TWO_CONTACT_PREPARED_NO_DISPATCH',s.sha(PROPOSAL),flush=True)


def authorize():
    assert not DESIGN.exists() and not BASE.exists()
    p=s.read(PROPOSAL);h=s.fields.sealed(DESIGNS/'human_approval_01/results.json')
    assert h['passed'] and h['proposal_sha256']==s.sha(PROPOSAL) and h['two_contact_probes_authorized'] is True
    s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['inputs'])
    local=s.ROOT/'paper1_runs/local_common_state_20261015'
    for rel in ('controller_01/launch.json','controller_01/worker_launch.json','worker_launch.json'):
        assert s.identity(s.read(local/rel))['retired']
    now=datetime.now(timezone.utc);end=now+timedelta(minutes=15)
    s.commit(DESIGN,{**p,'dispatch_authorized':True,'start_utc':now.isoformat(),'end_utc':end.isoformat(),
        'dispatch_cutoff_utc':(end-timedelta(minutes=1)).isoformat(),'proposal_sha256':s.sha(PROPOSAL),
        'human_approval_sha256':s.sha(DESIGNS/'human_approval_01/results.json')})


def bound():
    s.environment();p=s.read(DESIGN)
    assert p['dispatch_authorized'] and p['proposal_sha256']==s.sha(PROPOSAL)
    assert p['human_approval_sha256']==s.sha(DESIGNS/'human_approval_01/results.json')
    assert datetime.now(timezone.utc)<datetime.fromisoformat(p['end_utc'])
    assert shutil.disk_usage(s.ROOT).free>20*1024**3
    assert sum(x.stat().st_size for x in BASE.rglob('*') if x.is_file())<32*1024**2
    assert sum(x.stat().st_size for name in ('paper1_runs','paper1_designs','paper1_evaluations')
               for x in (s.ROOT/name).rglob('*') if x.is_file())<20*1024**3
    return p


def worker(index,mode):
    assert mode in ('primary','fallback') and 0<=index<4
    p=bound()
    namespace={**old.worker.__globals__,**globals(),'END':p['end_utc']}
    fn=FunctionType(old.worker.__code__,namespace,old.worker.__name__,old.worker.__defaults__,old.worker.__closure__)
    assert fn.__code__ is old.worker.__code__
    fn(index,mode)


def run():
    p=bound();s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['inputs'])
    BASE.mkdir(parents=True,exist_ok=False);me=psutil.Process();me.cpu_affinity([14])
    s.commit(BASE/'controller_launch.json',dict(pid=me.pid,created=me.create_time(),command=me.cmdline(),utc=s.utc()))
    calls=0;completed=0;reports=[];error=None
    try:
        for fixture in p['fixtures']:
            pair={}
            for mode in ('primary','fallback'):
                bound();assert datetime.now(timezone.utc)<datetime.fromisoformat(p['dispatch_cutoff_utc']) and calls<8
                calls+=1;folder=BASE/f"call_{fixture['fixture_id']:02d}_{mode}";folder.mkdir(exist_ok=False)
                cmd=[str(s.PYTHON),'-B','-u',str(SELF),'worker',str(fixture['fixture_id']),mode]
                with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
                    proc=subprocess.Popen(cmd,cwd=s.ROOT,env=os.environ.copy(),stdout=stdout,stderr=stderr,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    launch=dict(pid=proc.pid,created=psutil.Process(proc.pid).create_time(),command=cmd)
                    s.commit(folder/'launch.json',launch)
                    try:code=proc.wait(timeout=min(45,max(.1,datetime.fromisoformat(p['end_utc']).timestamp()-time.time())))
                    except subprocess.TimeoutExpired:
                        s.stop_owned(proc,launch);proc.wait(timeout=10);raise RuntimeError('Bounded identical-input probe timeout')
                assert s.identity(launch)['retired']
                s.commit(folder/'exit.json',dict(returncode=code,logs={str(x):s.sha(x) for x in folder.glob('*.log')},utc=s.utc()))
                assert code==0
                answer=s.fields.sealed(folder/'results.json');assert answer['passed'] and answer['independent_physics']['passed']
                completed+=1;pair[mode]=answer
            speed=s.read(fixture['path'])['speed_m_s']
            diff=float(np.linalg.norm(np.asarray(pair['primary']['answer'][0])-np.asarray(pair['fallback']['answer'][0]))/speed)
            reports.append(dict(fixture_id=fixture['fixture_id'],difference_over_U=diff,primary_archive_bits=pair['primary']['primary_archive_bits']))
            print('TWO_CONTACT_PAIR',fixture['fixture_id'],diff,flush=True)
    except Exception as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc());raise
    finally:
        s.api.verify_mapping(p['source_files']);s.api.verify_mapping(p['inputs'])
        artifacts={str(x):s.sha(x) for x in BASE.rglob('*') if x.is_file() and 'final_01' not in x.parts}
        s.seal(BASE/'final_01',dict(passed=error is None,error=error,attempted_contact_calls=calls,completed_contact_calls=completed,
            unknown_or_unqualified_contact_calls=calls-completed,prior_nonadvancing_contact_reservations=11,
            total_shared_nonadvancing_contact_reservations=11+calls,new_transport_steps=0,new_saved_steps=0,
            reports=reports,artifacts=artifacts,source_files=p['source_files'],inputs=p['inputs'],
            original_full_path_admission=False,production_authorized=False,successor_dispatch_authorized=False,utc=s.utc()))


if __name__=='__main__':
    if sys.argv[1]=='worker':worker(int(sys.argv[2]),sys.argv[3])
    else:{'prepare':prepare,'authorize':authorize,'run':run}[sys.argv[1]]()
