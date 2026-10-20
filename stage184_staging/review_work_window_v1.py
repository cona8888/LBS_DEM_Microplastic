"""Read-only numerical synthesis of the extended audited conditional paths.

No simulated continuation, production launch, physical calibration or release
inference. Distinct repeated verification trajectories are counted, never
concatenated as if they were new physical observation time.
"""
from pathlib import Path
import copy,datetime,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage180_staging'),str(ROOT/'stage181_staging'),str(ROOT/'stage182_staging'),str(ROOT/'stage183_staging')]
import qualify_real_trace_streaming_v1 as earlier
import qualify_runtime_deadline_v1 as extension
import bounded_live_audit_v1 as live
import qualify_fallback_evidence_v1 as fallback
import test_fallback_audit_edges_v1 as edge
api,parent=earlier.api,earlier.parent
DESIGN=ROOT/'stage184_designs/work_window_review_20260924/design_01.json'
RUN=ROOT/'stage184_runs/work_window_review_20260924/derived_traces_01'
OUT=ROOT/'stage184_evaluations/work_window_review_20260924/review_01'


def prepare():
    owners=[earlier,extension,live,fallback,edge];inputs=[]
    for owner in owners:
        owner.verify(api.read(owner.DESIGN));r=api.read(owner.OUT/'results.json')
        api.require(r['passed'] and api.read(owner.OUT/'completion.json')['results_sha256']==api.sha(owner.OUT/'results.json'),'all prerequisite completions')
        if 'artifacts' in r:api.verify_mapping(r['artifacts'])
        inputs.extend([owner.DESIGN,owner.OUT/'results.json',owner.OUT/'completion.json'])
    work=ROOT/'stage172_designs/four_hour_work_20260923/contract_01.json';inputs.append(work)
    d={'stage':'Stage184 work-window numerical review','physical_changes':[],'new_trajectory_steps':0,
        'sources':parent.source_map(),'inputs':{str(p):api.sha(p) for p in inputs},'limits':api.read(earlier.DESIGN)['limits'],
        'cutoff_utc':api.read(work)['end_utc'],'work_step_cap':250000,
        'new_step_ledger':[{'stage':172,'steps':16079},{'stage':173,'steps':1120},{'stage':174,'steps':33976},
            {'stage':175,'steps':18000},{'stage':177,'steps':132000},{'stage':181,'steps':6000},{'stage':182,'steps':36000},{'stage':183,'steps':6500}],
        'claim':'Extended conditional selected-versus-fine numerical comparison, not full-path accuracy or release. Repeated tests excluded from physical time concatenation.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(exist_ok=True,parents=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    for owner in [earlier,extension,live,fallback,edge]:owner.verify(api.read(owner.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);start=time.perf_counter();artifacts={}
    e=api.read(earlier.OUT/'results.json');cases=copy.deepcopy(e['cases']);ed=api.read(extension.DESIGN);ld=api.read(live.DESIGN)
    for name,case in cases.items():
        cp=extension.independent.independent_read(extension.prior.RUN/name/'segment_002.json.xz',api.sha(extension.prior.DESIGN))['result']['checkpoint']
        api.require(cp['state']['t']==case['end_s'],'earlier audited endpoint')
        entries=case['entries'];folder=RUN/name;folder.mkdir()
        spec=next(c['spec'] for c in ed['cases'] if c['id']==name);binding=api.digest([ed['binding'],name]);before=parent.model.checkpoint(spec,binding,cp,True)
        rec,_=extension.codec.read_record(extension.RUN/(name+'.json.xz'),api.sha(extension.DESIGN))
        api.require(rec['input_checkpoint_sha256']==api.digest(before),'Stage181 physical checkpoint continuity')
        arr=np.array([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
        path=folder/'deadline_identity_extension.npy'
        with path.open('xb') as f:np.save(f,arr,allow_pickle=False)
        entries.append({'trace':str(path),'trace_sha256':api.sha(path),'rows':len(arr),'start_s':before['state']['t'],'stop_s':rec['result']['time_s'],
            'physics_audit_receipt':str(extension.OUT/'results.json'),'physics_audit_sha256':api.sha(extension.OUT/'results.json')});artifacts[str(path)]=api.sha(path)
        cp=rec['result']['checkpoint'];binding=api.digest([ld['binding'],name]);cp=parent.model.checkpoint(spec,binding,cp,True);prefix=None
        for i in range(1,ld['blocks_per_case']+1):
            paths=live.location(name,i);marker=api.read(paths['ready']);receipt=api.read(paths['receipt']);live.verify_ready(marker,paths,{'id':name},i,ld,cp)
            rec,prefix=live.codec.read_record(paths['raw'],api.sha(live.DESIGN),prefix)
            api.require(receipt['summary']['passed'] and receipt['input_checkpoint_sha256']==api.digest(cp) and receipt['raw_sha256']==api.sha(paths['raw']),'independent live audit continuation')
            api.require(receipt['trace_sha256']==api.sha(paths['trace']) and receipt['original_raw_sha256']==prefix.original_sha256,'raw and trace seals')
            entries.append({'trace':str(paths['trace']),'trace_sha256':receipt['trace_sha256'],'rows':receipt['summary']['steps'],
                'start_s':receipt['summary']['start_s'],'stop_s':receipt['summary']['stop_s'],'physics_audit_receipt':str(paths['receipt']),'physics_audit_sha256':api.sha(paths['receipt'])})
            cp=rec['result']['checkpoint']
        case['end_s']=cp['state']['t'];case['final_state_sha256']=cp['state_sha256'];case['full_observation']=False
    def blocks(c):
        for entry in c['entries']:
            api.require(api.sha(entry['trace'])==entry['trace_sha256'] and api.sha(entry['physics_audit_receipt'])==entry['physics_audit_sha256'],'all source/receipt seals')
            arr=np.load(entry['trace'],mmap_mode='r',allow_pickle=False);api.require(arr.shape==(entry['rows'],13),'audited trace dimensions');yield arr
    comparisons=[]
    for shape in ['rigid_prolate_ar4','equal_volume_sphere']:
        a=next(c for c in cases.values() if c['shape']==shape and c['factor']==2.)
        b=next(c for c in cases.values() if c['shape']==shape and c['factor']==1.)
        cfg=b['spec']['config'];m=earlier.candidate.metrics(blocks(a),blocks(b),a['initial'],b['initial'],a['end_s'],b['end_s'],cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
        values={'pose_b':m['whole_position_over_b_max'],'axis':m['whole_axis_vector_norm_max'],'endpoint_velocity_U':m['endpoint_q_over_U_max'],'mean_L1_velocity_U':m['mean_L1_q_over_U_max']}
        comparisons.append({'shape':shape,'values':values,'limits':d['limits'],'passed':all(v<=d['limits'][k] for k,v in values.items()),'streaming_detail':m})
        print('EXTENDED_COMPARE',shape,values,flush=True)
    total=sum(x['steps'] for x in d['new_step_ledger']);api.require(total==249675<=d['work_step_cap'],'complete work-window step ledger')
    api.require(total==api.read(fallback.OUT/'results.json')['work_cumulative_steps'],'latest cumulative independent count')
    verify(d);api.verify_mapping(artifacts);passed=all(c['passed'] for c in comparisons)
    report={'passed':passed,'comparisons':comparisons,'cases':cases,'artifacts':artifacts,'new_step_ledger':d['new_step_ledger'],'work_window_total_steps':total,
        'remaining_step_allowance':d['work_step_cap']-total,'new_trajectory_steps':0,'wall_seconds':time.perf_counter()-start,'design_sha256':api.sha(DESIGN),
        'cutoff_utc':d['cutoff_utc'],'claim':d['claim'],'no_production_run':True,'no_complete_full_path_observation':True,
        'remaining_before_future_campaign':['fresh frozen six-case launcher/design with revised cutoff','parallel slowdown/identity preflight for the new full stack','full-path execution with incremental audits','terminal selected/fine comparison; report all censored/incomplete cases']}
    api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')});print('WORK_REVIEW',passed,total,flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
