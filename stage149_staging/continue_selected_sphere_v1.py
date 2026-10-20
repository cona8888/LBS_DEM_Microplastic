"""One bounded selected-sphere continuation after Stage148 qualification.

No population dispatch, no new physics, no trajectory time skips. Preserve every
segment, exact clock chain, certificate summary and finite nonabsorbing dwell.
"""
from pathlib import Path
import copy
import gzip
import json
import os
import sys
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage148_staging'),str(ROOT/'stage142_staging')]
import compiled_geometric_contract_v1 as method
import audit_clock_and_seal_v1 as audit
import progress_guard_v1 as guard
parent=method.parent
api,engine,hot=parent.api,parent.engine,parent.hot
QUAL=audit.OUT
RUN=ROOT/'stage149_runs/selected_sphere_cpd6_0p1pv_20260921/continuation_01'
OUT=ROOT/'stage149_evaluations/selected_sphere_cpd6_0p1pv_20260921/evaluation_01'


class Certificates:
    def __init__(self):
        self.data={'count':0,'all_passed':True,'legacy_energy_gate_violations':0,
                   'max_raw_residual_over_vfree':0.,'max_residual_over_ceiling':0.,
                   'max_force_residual':0.,'max_positive_friction_work_W':0.,
                   'sum_positive_friction_work_dt_J_all_outer_solves':0.,
                   'maximum_delta_geom_m':0.}
        self.worst=None

    def append(self, c):
        d=self.data;d['count']+=1;d['all_passed'] &= c['passed']
        d['legacy_energy_gate_violations']+=int(not c['legacy_work_gate_pass'])
        if c['residual_over_ceiling']>d['max_residual_over_ceiling']:
            self.worst=c
        for key,source in [('max_raw_residual_over_vfree','legacy_residual_over_vfree'),
                           ('max_residual_over_ceiling','residual_over_ceiling'),
                           ('max_force_residual','force_residual'),
                           ('max_positive_friction_work_W','friction_work_W'),
                           ('maximum_delta_geom_m','delta_geom_m')]:
            d[key]=max(d[key],c[source])
        # A conservative work diagnostic, not a physical energy integral: outer
        # iterates may repeat the same interval and are deliberately all counted.
        d['sum_positive_friction_work_dt_J_all_outer_solves']+=max(0.,c['friction_work_W'])*c['dt_s']


def main():
    q=api.read(QUAL/'results.json')
    api.require(q['qualification_passed'] and api.sha(QUAL/'results.json')==api.read(QUAL/'completion.json')['results_sha256'],'Stage148 qualification')
    prior=api.read(audit.SOURCE/'results.json');api.verify_mapping(prior['artifacts'])
    qp=api.read(audit.SOURCE/'protocol.json');api.verify_mapping(qp['sources']);api.verify_mapping(qp['inputs'])
    pd=api.read(parent.DESIGN);parent.verify(pd)
    c=next(c for c in pd['cases'] if c['id']=='sphere_12_terminal')
    spec=copy.deepcopy(c['spec'])
    spec['config']['numerics']['wall_budget_s_per_case']=40.
    cp=copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
    api.require(cp['state_sha256']==api.digest(cp['state']) and cp['state']['pending_trial'] is None,'source checkpoint')
    inputs=[QUAL/'results.json',QUAL/'completion.json',audit.SOURCE/'protocol.json',parent.DESIGN,Path(c['source'])]
    protocol={'stage':'Stage149','case':c['id'],'spec':spec,'initial_time_s':cp['state']['t'],
              'question':'Can normal integration of this selected sphere reach the already frozen 0.1 PV horizon with the locally qualified compiled geometric contract?',
              'numerical_change':'Stage148 sphere-only contract enabled, kappa=16. No inertia restoration, warm starts, enumeration or equilibrium time skip.',
              'acceptance':{'horizon_exact':spec['horizon_s'],'all_health_gates':True,'every_contact_certified':True,
                            'exact_clock_chain':True,'no_unqualified_fallback':True,'immutable_hash_chain':True,
                            'dwell_absorbing':False,'pose_within_coordinate_scale_L':True},
              'budget':{'segment_s':40.,'maximum_segments':12,'total_dispatch_s':550.,'max_new_steps_per_segment':30000},
              'stop_on': ['numerical failure','independent health failure','no useful progress','budget exhausted','horizon or full-body outlet exit'],
              'not_claimed':['Population release fraction','Full-path timestep convergence','Experimental validation','Irreversible retention','Fibre trajectory qualification'],
              'inputs':{str(p):api.sha(p) for p in inputs},
              'sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,method.__file__,audit.__file__,guard.__file__]}}
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    api.write(RUN/'protocol.json',protocol)
    binding=api.digest([api.sha(RUN/'protocol.json'),'selected_sphere'])
    cp['contract']=engine.prior.contracts.expected_contract(spec,binding)
    api.write(RUN/'launch.json',{'pid':os.getpid(),'command':sys.argv,'binding':binding,'protocol_sha256':api.sha(RUN/'protocol.json')})
    parent.old.prior.prior.configure();hot.warmup()
    started=time.perf_counter();ledger=[];initial=copy.deepcopy(cp);failure=None
    for number in range(1,13):
        if time.perf_counter()-started+45>550: break
        folder=RUN/f'segment_{number:02d}';folder.mkdir(exist_ok=False)
        before=copy.deepcopy(cp)
        api.require(cp['state_sha256']==api.digest(cp['state']),'checkpoint chain')
        collector=Certificates()
        with hot.scope(),parent.scope(spec),method.scope(spec,enabled=True,multiplier=16,certificates=collector):
            r,rows=engine.runtime.execute(spec,binding,checkpoint=cp,pause=cp['state']['steps']+30000)
        health=engine.prior.reference.independent_health(r,spec)
        clock=audit.clock_chain(before['state']['t'],rows,r['time_s'])
        coordinates=all(max(np.abs(x['position_m'])) <= spec['field_metadata']['cell_length_m'] for x in rows)
        record_ok=(health['passed'] and clock['passed'] and coordinates and collector.data['all_passed']
                   and not r.get('stage119_repair_calls') and r['checkpoint']['state_sha256']==api.digest(r['checkpoint']['state'])
                   and len(rows)==r['steps']-before['state']['steps'])
        progress=guard.assess(before['state']['t'],r['time_s'],spec['horizon_s'],
                             spec['config']['numerics']['max_dt_s'],
                             'incomplete_budget' if r['status']=='paused_checkpoint' else r['status'])
        with gzip.open(folder/'intervals.json.gz','xb',compresslevel=1) as f:
            f.write(json.dumps(rows,sort_keys=True,allow_nan=False).encode())
        record={'result':r,'health':health,'clock_audit':clock,'passed':record_ok,
                'coordinate_scale_verified':coordinates,'contact_certificates':collector.data,'worst_contact_certificate':collector.worst,
                'progress':progress,'binding':binding,'protocol_sha256':api.sha(RUN/'protocol.json'),
                'input_checkpoint_sha256':api.digest(before),
                'previous_record_sha256':ledger[-1]['sha256'] if ledger else None,
                'intervals_sha256':api.sha(folder/'intervals.json.gz')}
        api.write(folder/'record.json',record,raw=True)
        api.write(folder/'completion.json',{'record_sha256':api.sha(folder/'record.json')})
        ledger.append({'path':str(folder/'record.json'),'sha256':api.sha(folder/'record.json'),
                       'passed':record_ok,'status':r['status'],'time_s':r['time_s'],'new_steps':len(rows)})
        print('SEGMENT',number,record_ok,r['status'],'t',r['time_s'],'steps',len(rows),'wall',r['runtime_seconds'],flush=True)
        cp=r['checkpoint']
        if not record_ok or r['status'] not in ('incomplete_budget','paused_checkpoint','present_at_horizon','full_window_exit'):
            failure='numerical_or_independent_health_failure';break
        if r['status'] in ('present_at_horizon','full_window_exit'): break
        if not progress['continue']:failure='no_useful_progress';break
    # Re-open every bundle independently of the live variables; verify chain,
    # exact clocks and final health once more, leaving all records immutable.
    independent=[];previous_cp=initial;previous_hash=None
    for entry in ledger:
        path=Path(entry['path']);record=api.read(path)
        api.require(api.sha(path)==entry['sha256']==api.read(path.parent/'completion.json')['record_sha256'],'record seal')
        api.require(api.sha(path.parent/'intervals.json.gz')==record['intervals_sha256'],'interval seal')
        with gzip.open(path.parent/'intervals.json.gz','rt') as f: rows=json.load(f)
        r=record['result']
        chain=(record['input_checkpoint_sha256']==api.digest(previous_cp) and record['previous_record_sha256']==previous_hash)
        clock=audit.clock_chain(previous_cp['state']['t'],rows,r['time_s'])
        health=engine.prior.reference.independent_health(r,spec)
        independent.append({'segment':path.parent.name,'passed':chain and clock['passed'] and health['passed'] and record['passed'],
                            'clock':clock,'health':health,'chain':chain})
        previous_cp=r['checkpoint'];previous_hash=api.sha(path)
    completed=bool(ledger and ledger[-1]['status']=='present_at_horizon' and ledger[-1]['time_s']==spec['horizon_s'])
    exited=bool(ledger and ledger[-1]['status']=='full_window_exit')
    passed=(completed or exited) and not failure and all(x['passed'] for x in independent)
    r=api.read(ledger[-1]['path'])['result'] if ledger else None
    api.verify_mapping(protocol['sources']);api.verify_mapping(protocol['inputs']);api.verify_mapping(qp['sources']);api.verify_mapping(qp['inputs'])
    result={'stage':'Stage149','passed':passed,'completed_horizon':completed,'full_body_exited':exited,
            'stop_reason':failure or ('horizon' if completed else 'outlet_exit' if exited else 'bounded_budget_exhausted'),
            'initial_time_s':initial['state']['t'],'final_time_s':r['time_s'] if r else None,
            'new_accepted_steps':sum(x['new_steps'] for x in ledger),'segments':ledger,'independent_evaluations':independent,
            'new_rejected_trials':r['rejected']-initial['state']['rejected'] if r else None,
            'finite_dwell_observed':r['persistent_contact_observed'] if r else None,
            'first_dwell_time_s':r['first_contact_dwell_time_s'] if r else None,
            'final_trap_state':r['trap_state'] if r else None,'dwell_is_absorbing':False,
            'displacement_over_b':float(np.linalg.norm(np.array(r['position_m'])-initial['state']['x'])/spec['config']['prolate_semiaxes_m'][1]) if r else None,
            'dispatch_wall_s':time.perf_counter()-started,
            'claim':'A selected saved sphere continuation only; finite-horizon presence/exit, not a resident-matrix release fraction or irreversible trapping. Full-duration refinement and fibre selection remain separate.',
            'protocol_sha256':api.sha(RUN/'protocol.json')}
    api.write(OUT/'results.json',result,raw=True)
    api.write(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json'),'protocol_sha256':api.sha(RUN/'protocol.json')})
    print('STAGE149_PASS',passed,result['stop_reason'],flush=True)
    return 0 if passed else 4


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        if OUT.exists() and not (OUT/'failure.json').exists():
            api.write(OUT/'failure.json',{'error':repr(exc),'traceback':traceback.format_exc()},raw=True)
        raise
