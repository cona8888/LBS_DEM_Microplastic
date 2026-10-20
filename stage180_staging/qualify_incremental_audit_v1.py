"""Audit immutable prefix records one at a time; seal independent receipts.

All sources are already finished local windows. This tests incremental audit
semantics and replay without launching or following a production campaign.
"""
from pathlib import Path
import copy,datetime,math,sys,time,traceback
import numpy as np
import audit_optimized_record_v1 as kernel
ROOT=kernel.ROOT;api,parent=kernel.api,kernel.parent
sys.path.insert(0,str(ROOT/'stage179_staging'))
import qualify_history_prefix_v1 as sources
import audit_history_prefix_v1 as prefix_audit
codec=sources.codec;original=sources.prior
DESIGN=ROOT/'stage180_designs/incremental_audit_20260924/raw_audit_design_01.json'
RUN=ROOT/'stage180_runs/incremental_audit_20260924/raw_receipts_01'
OUT=ROOT/'stage180_evaluations/incremental_audit_20260924/raw_audit_01'


def prepare():
    p=api.read(prefix_audit.OUT/'results.json');api.require(p['passed'],'independent lossless prefix prerequisite')
    inputs=[sources.DESIGN,sources.OUT/'results.json',sources.OUT/'completion.json',prefix_audit.OUT/'results.json',prefix_audit.OUT/'completion.json',original.DESIGN]
    rows=api.read(sources.OUT/'results.json')['records']
    for row in rows:inputs.extend([Path(row['output']),Path(row['output']).with_suffix('.seal.json')])
    original_audit=original.OUT.parent/'independent_audit_01/results.json';inputs.extend([original_audit,original_audit.parent/'completion.json'])
    d={'stage':'Stage180 incremental raw audit qualification','physical_changes':[],'new_trajectory_steps':0,'raw_design_sha256':api.sha(original.DESIGN),
       'records':rows,'sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,kernel.__file__,kernel.verified.__file__,kernel.exit_event.__file__,codec.__file__,codec.base.__file__]},
       'inputs':{str(p):api.sha(p) for p in inputs},'source_cases':api.read(original.DESIGN)['cases'],
       'gap_semantics':api.read(original.DESIGN)['minimum_gap_semantics'],'maximum_wall_seconds':900,'cutoff_utc':'2026-09-24T02:46:55+00:00',
       'claim':'Fresh independent per-record physics/clock/dwell audit of 132,000 existing local steps, plus geometric terminal-helper units. No production simulation.'}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    sources.verify(api.read(sources.DESIGN));original.verify(api.read(original.DESIGN))


def event_units():
    checked=[];guards=[];a=2e-4;b=5e-5;L=.00468;U=1e-4;trial=1e-5
    def check(x,p,q,aa,bb,dt,tt,status='full_window_exit',last=True):
        end_x,end_p=kernel.exit_event.mechanics.advance_pose(np.array(x),np.array(p),np.array(q),aa,dt)
        event=kernel.interval_geometry(x,p,q,aa,bb,L,dt,tt,end_x,end_p,last,status)
        kernel.terminal_label(status,dt,1.,event is not None);return event
    for shape,aa,bb,p in [('sphere',b,b,[1.,0.,0.]),('fibre_aligned',a,b,[1.,0.,0.]),('fibre_transverse',a,b,[0.,1.,0.])]:
        extent=math.sqrt(bb*bb+(aa*aa-bb*bb)*p[0]**2);x=[L+extent-U*trial*.4,.001,.001];q=[U,0.,0.,0.,0.,0.]
        event=kernel.exit_event.linear_pose_exit_time(x,p,q,aa,bb,L,trial)
        api.require(event is not None and 0<event<trial,'positive truncated whole-body event')
        api.require(check(x,p,q,aa,bb,event,trial)==event,'accepted exit prefix verified');checked.append(shape)
    omega=1000.;x=[L+(a+b)/2,.001,.001];p=[1.,0.,0.];q=[0.,0.,0.,0.,0.,a*omega];trial=2*math.pi/omega
    event=kernel.exit_event.linear_pose_exit_time(x,p,q,a,b,L,trial)
    analytical=math.acos(math.sqrt((((a+b)/2)**2-b*b)/(a*a-b*b)))/omega
    api.require(abs(event-analytical)<=1e-14 and check(x,p,q,a,b,event,trial)==event,'first exit-and-return event');checked.append('rotating_exit_and_return')
    def reject(label,fn):
        try:fn()
        except (ValueError,RuntimeError):guards.append(label);return
        raise AssertionError('event guard accepted '+label)
    reject('later_crossing_not_first',lambda:check(x,p,q,a,b,trial-event,trial))
    reject('export_not_last_row',lambda:check(x,p,q,a,b,event,trial,last=False))
    reject('unlabelled_export',lambda:check(x,p,q,a,b,event,trial,status='paused_checkpoint'))
    reject('centre_only_crossing',lambda:check([L-b/2,.001,.001],[1.,0.,0.],[U,0.,0.,0.,0.,0.],b,b,b/U,b/U))
    reject('premature_horizon',lambda:kernel.terminal_label('present_at_horizon',.9,1.,False))
    reject('horizon_label_missing',lambda:kernel.terminal_label('paused_checkpoint',1.,1.,False))
    reject('false_export_label',lambda:kernel.terminal_label('full_window_exit',.5,1.,False))
    kernel.terminal_label('present_at_horizon',1.,1.,False)
    return {'geometric_cases':checked,'rejected_labels':guards,'exact_horizon_label':True,'trajectory_steps':0,'kind':'geometric audit-helper units only'}


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);started=time.perf_counter();artifacts={};results=[]
    try:
        units=event_units();parent.b.old.parent.configure();field,data,meta=api.fields.load(2,1.,6)
        geometry=kernel.verified.job.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
        old_results=api.read(original.OUT.parent/'independent_audit_01/results.json');old_rows={x['path']:x for x in old_results['record_audits']}
        example=None
        for c in d['source_cases']:
            folder=RUN/c['id'];folder.mkdir();source=parent.storage.read_record(Path(c['source']),c['source_design_sha256']);binding=api.digest([api.read(original.DESIGN)['binding'],c['id']])
            seed=parent.model.checkpoint(c['spec'],binding,source['result']['checkpoint'],True);prefix_states=[];checkpoints=[];receipts=[]
            rows=[x for x in d['records'] if Path(x['source']).parent.name==c['id']]
            for i,row in enumerate(rows):
                api.require(time.perf_counter()-started<d['maximum_wall_seconds'] and datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(d['cutoff_utc']),'bounded audit work')
                pi=row['parent_index'];prefix=prefix_states[pi] if pi is not None else None;before=checkpoints[pi] if pi is not None else seed
                rec,prefix_state=codec.read_record(row['output'],d['raw_design_sha256'],prefix)
                summary=kernel.evaluate(rec,c['spec'],binding,before,geometry,d['raw_design_sha256'],d['gap_semantics'])
                expected=old_rows[row['source']]
                api.require(summary['steps']==expected['steps'] and summary['certified_sweeps']==expected['certified'] and summary['early_force_systems']==expected['early'],'prior independent count agreement')
                trace=np.array([[x['time_s'],*x['position_m'],*x['orientation'],*x['velocity_generalized']] for x in rec['rows']],dtype=np.float64)
                tracepath=folder/f'block_{i+1:03d}.npy'
                with tracepath.open('xb') as f:np.save(f,trace,allow_pickle=False)
                receipt={'case':c['id'],'raw_prefix_path':row['output'],'raw_prefix_sha256':api.sha(row['output']),
                    'raw_seal_sha256':api.sha(Path(row['output']).with_suffix('.seal.json')),'original_raw_sha256':prefix_state.original_sha256,
                    'trace_path':str(tracepath),'trace_sha256':api.sha(tracepath),'input_checkpoint_sha256':api.digest(before),
                    'previous_receipt_sha256':receipts[pi]['sha256'] if pi is not None else None,'summary':summary,
                    'audit_design_sha256':api.sha(DESIGN),'kernel_sha256':api.sha(kernel.__file__),'status':'independently_verified'}
                path=folder/f'block_{i+1:03d}.audit.json';api.write(path,receipt)
                receipts.append({'path':str(path),'sha256':api.sha(path)});prefix_states.append(prefix_state);checkpoints.append(rec['result']['checkpoint']);results.append(receipt)
                for p in [path,tracepath]:artifacts[str(p)]=api.sha(p)
                if i==3:example=(rec,c['spec'],binding,before)
                print('INCREMENTAL_AUDIT',c['id'],i,summary['steps'],round(summary['audit_seconds'],3),flush=True)
        # Corrupt copies are kept in memory only. No original evidence is edited.
        rec,spec,binding,before=example;guards=[]
        for label,change in [('missing_proof',lambda r:r['sweep_certificates'].pop()),('bad_checkpoint_hash',lambda r:r['result']['checkpoint'].update(state_sha256='0'*64)),
                             ('false_horizon',lambda r:r['result'].update(status='present_at_horizon')),('false_export',lambda r:r['result'].update(status='full_window_exit')),
                             ('undeclared_gap_semantics',lambda r:r.update(minimum_gap_semantics='measured minimum'))]:
            bad=copy.deepcopy(rec);change(bad)
            try:kernel.evaluate(bad,spec,binding,before,geometry,d['raw_design_sha256'],d['gap_semantics'])
            except (RuntimeError,ValueError):guards.append(label)
            else:raise AssertionError('raw audit guard accepted '+label)
        # Resume/replay verifies sealed receipts and raw/trace hashes without
        # silently creating another receipt or repeating already committed work.
        verify(d);api.verify_mapping(artifacts);known=set()
        for receipt in results:
            api.require(receipt['previous_receipt_sha256'] is None or receipt['previous_receipt_sha256'] in known,'receipt ancestor already verified')
            api.require(api.sha(receipt['raw_prefix_path'])==receipt['raw_prefix_sha256'] and api.sha(receipt['trace_path'])==receipt['trace_sha256'],'resume input/artifact identity')
            path=next(Path(p) for p in artifacts if p.endswith('.audit.json') and api.read(p)==receipt);known.add(api.sha(path))
        totals={k:sum(x['summary'][k] for x in results) for k in ['steps','certified_sweeps','legacy_sweeps','early_force_systems']}
        api.require(totals['steps']==132000 and len(results)==30,'complete incremental coverage')
        report={'passed':True,'totals':totals,'receipts':results,'artifacts':artifacts,'event_units':units,'raw_guard_rejections':guards,
                'resume_receipt_replay_passed':True,'new_trajectory_steps':0,'wall_s':time.perf_counter()-started,'design_sha256':api.sha(DESIGN),
                'claim':d['claim'],'production_ready':False,'unsupported':'Unrecorded fallback force systems and zero-accepted-step records fail closed rather than being declared verified.'}
        api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('INCREMENTAL_PASS',totals,flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'receipts_completed':len(results),'new_trajectory_steps':0});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
