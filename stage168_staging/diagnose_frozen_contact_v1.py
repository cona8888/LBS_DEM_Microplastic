"""Bounded fixed-pose algebraic diagnosis, never trajectory integration."""
from pathlib import Path
import collections
import copy
import datetime
import inspect
import sys
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage167_staging'))
import paired_deadline_campaign_v1 as parent
api=parent.api
diag=parent.b.q.diag
BASE='sphere_three_contact_diagnosis_20260923'
DESIGN=ROOT/'stage168_designs'/BASE/'design_01.json'
OUT=ROOT/'stage168_evaluations'/BASE/'capture_01'


def prepare():
    old=api.read(parent.DESIGN);parent.verify(old)
    failure=parent.OUT.parent/'failure_assessment_01/results.json'
    ev=api.read(failure)
    api.require(ev['audit_integrity_passed'] and not ev['scientific_gates_passed'],'verified failure')
    raw=Path(ev['failed_segment']['path']); record=parent.storage.read_record(raw,api.sha(parent.DESIGN))
    t=ev['first_rejection']['time_s']; rows=record['rows']
    idx=next(i for i,r in enumerate(rows) if r['time_s']==t)
    states=[]
    for name,i,target_dt in [('preceding_good',idx-1,rows[idx]['dt_s']),('first_rejected',idx,ev['first_rejection']['dt_s'])]:
        row=rows[i]
        states.append({'id':name,'state':{'x':row['position_m'],'p':row['orientation'],'q':row['velocity_generalized'],'t':row['time_s'],'recovery':False},
                       'dt_s':target_dt,'expected_velocity':rows[idx]['velocity_generalized'] if name=='preceding_good' else None,
                       'expected_error':ev['first_rejection']['reason'] if name=='first_rejected' else None})
    files=[parent.DESIGN,failure,failure.with_name('completion.json'),raw,raw.with_suffix('.seal.json')]
    cfg=record['spec']['field_metadata']
    for key in ['geometry','field']:
        if isinstance(cfg.get(key),dict) and 'path' in cfg[key]:files.append(Path(cfg[key]['path']))
    design={'stage':'Stage168','authorization':'User yes to focused contact-solver diagnosis, without trajectory rerun.',
        'question':'Does the archived failure reproduce at its exact frozen pose, and which unchanged contact acceptance test rejects the algebraic candidate?',
        'spec':record['spec'],'probes':states,'maximum_frozen_pose_calls':2,'maximum_finish_records':200,
        'physical_changes':[],'trajectory_steps_authorized':0,'claim':'Fixed-pose solver diagnosis only, not a repaired or qualified model.',
        'inputs':{str(p):api.sha(p) for p in files},'sources':parent.source_map()}
    design['binding']=api.digest(design);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,design)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['inputs']);api.verify_mapping(d['sources']);parent.verify(api.read(parent.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);OUT.mkdir(parents=True,exist_ok=False)
    parent.b.old.parent.configure()
    spec=d['spec'];field,data,metadata=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],metadata['cell_length_m'])
    captures=[];probes=[];current=None
    hot=parent.b.old.hot
    with hot.scope(),parent.fix.scope():
        original=hot.s50._finish;compiled_original=hot.PRIMARY.__globals__['_finish']
        def capture(*args,**kwargs):
            api.require(len(captures)<d['maximum_finish_records'],'bounded fixed-pose capture')
            names=['vfree','mobility','jacobian','force','z','A','gaps','dt','friction','steps','iterations','solver','extra']
            payload={k:copy.deepcopy(v) for k,v in zip(names,args)};payload.update(kwargs)
            payload['probe_id']=current
            start=time.perf_counter()
            try:
                answer=original(*args,**kwargs)
            except Exception as error:
                payload.update(accepted=False,error=str(error));raise
            else:
                payload.update(accepted=True,velocity=answer[0],health=answer[1]);return answer
            finally:
                payload['gate_seconds']=time.perf_counter()-start
                path=OUT/f'system_{len(captures):03d}.json'
                api.write(path,payload,raw=True);captures.append({'path':str(path),'sha256':api.sha(path),'accepted':payload['accepted'],'probe_id':current,'error':payload.get('error')})
        hot.s50._finish=capture;hot.PRIMARY.__globals__['_finish']=capture
        try:
            for probe in d['probes']:
                current=probe['id'];start=time.perf_counter()
                try:q,detail=diag.replay(field,geometry,spec,probe['state'],probe['dt_s'])
                except RuntimeError as error:
                    result={'id':current,'error':str(error),'expected_failure_reproduced':str(error)==probe['expected_error']}
                else:
                    result={'id':current,'detail':detail,'velocity':q.tolist(),'error':None,
                        'replay_difference_over_U':float(np.linalg.norm(q-probe['expected_velocity'])/spec['config']['target_mean_interstitial_velocity_m_s']) if probe['expected_velocity'] is not None else None}
                result['wall_s']=time.perf_counter()-start;probes.append(result)
        finally:hot.s50._finish=original;hot.PRIMARY.__globals__['_finish']=compiled_original
    good,bad=probes
    checks={'preceding_good_replayed':good['error'] is None and good['replay_difference_over_U']<=1e-8,
            'first_rejection_reproduced':bad.get('expected_failure_reproduced',False),
            'failed_gate_captured':any(not x['accepted'] and x['probe_id']=='first_rejected' for x in captures)}
    verify(d)
    result={'diagnostic_integrity_passed':all(checks.values()),'checks':checks,'probes':probes,'systems':captures,
        'trajectory_steps_advanced':0,'production_changed':False,'design_sha256':api.sha(DESIGN),'claim':d['claim']}
    api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'diagnostic_integrity_passed':result['diagnostic_integrity_passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('CAPTURE',checks,'systems',len(captures),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare or run')
