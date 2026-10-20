"""Immutable per-record trace extraction and bounded-block comparison on real paths.

Uses existing independent physics-audit receipts; no numerical integration.
Receipts explicitly distinguish reused raw audits from fresh trace extraction.
"""
from pathlib import Path
import sys,time
import numpy as np
import streaming_path_metrics_v2 as candidate
import qualify_streaming_metrics_v2 as units
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage178_staging'))
import compare_extended_conditional_paths_v1 as previous
api,parent=previous.api,previous.parent
DESIGN=ROOT/'stage180_designs/incremental_audit_20260924/real_trace_design_01.json'
RUN=ROOT/'stage180_runs/incremental_audit_20260924/trace_blocks_01'
OUT=ROOT/'stage180_evaluations/incremental_audit_20260924/real_traces_01'


def prepare():
    p=api.read(previous.OUT/'results.json');u=api.read(units.OUT/'results.json')
    api.require(p['passed'] and u['passed'],'trace and metric prerequisites')
    sources=[__file__,candidate.__file__,candidate.base.__file__,previous.__file__]
    inputs=[previous.DESIGN,previous.OUT/'results.json',previous.OUT/'completion.json',units.DESIGN,units.OUT/'results.json',units.OUT/'completion.json']
    d={'stage':'Stage180 real trace streaming','new_trajectory_steps':0,'physical_changes':[],'cases':api.read(previous.DESIGN)['cases'],
       'sources':{str(Path(p).resolve()):api.sha(p) for p in sources},'inputs':{str(p):api.sha(p) for p in inputs},
       'columns':['time_s','x','y','z','px','py','pz','vx','vy','vz','a_omega_x','a_omega_y','a_omega_z'],
       'limits':p['limits'],'oracle_rtol':1e-10,'oracle_atol':1e-12,
       'claim':'File-backed numerical comparison on already-audited conditional paths. No new whole-path or empirical claim.'}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);previous.verify(api.read(previous.DESIGN))


def run():
    d=api.read(DESIGN);verify(d);RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);cases={};artifacts={};start=time.perf_counter()
    for case,info in d['cases'].items():
        folder=RUN/case;folder.mkdir();module=previous.fibre if info['shape']=='rigid_prolate_ar4' else previous.sphere;sd=api.read(module.DESIGN)
        if module is previous.fibre:spec,binding,cp=module.setup(sd,info['factor'],'certificate')
        else:spec,binding,cp=module.p.setup(sd,info['factor'])
        initial=np.array([cp['state']['t'],*cp['state']['x'],*cp['state']['p'],*cp['state']['q']]);entries=[];chain=None
        for phase,owner in [('initial',module),('middle',previous.latest.prior),('latest',previous.latest)]:
            if phase!='initial':
                dd=api.read(owner.DESIGN);c=next(x for x in dd['cases'] if x['id']==case);api.require(c['initial_checkpoint_state_sha256']==cp['state_sha256'],'cross-stage state link')
                spec=c['spec'];binding=api.digest([dd['binding'],case]);cp=parent.model.checkpoint(spec,binding,cp,True)
            for name in info[phase]:
                source=Path(name);rec=previous.latest_audit.independent_read(source,api.sha(owner.DESIGN)) if phase=='latest' else parent.storage.read_record(source,api.sha(owner.DESIGN))
                api.require(rec['input_checkpoint_sha256']==api.digest(cp),'trace physical chain')
                arr=np.array([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
                api.require(np.isfinite(arr).all() and arr[0,0]>cp['state']['t'] and np.all(np.diff(arr[:,0])>0),'finite strict trace clock')
                path=folder/f'trace_{len(entries)+1:03d}.npy'
                with path.open('xb') as f:np.save(f,arr,allow_pickle=False)
                receipt={'source':name,'source_sha256':api.sha(source),'source_seal_sha256':api.sha(source.with_suffix('.seal.json')),
                         'source_design_sha256':api.sha(owner.DESIGN),'trace':str(path),'trace_sha256':api.sha(path),'rows':len(arr),'start_s':cp['state']['t'],'stop_s':float(arr[-1,0]),
                         'input_checkpoint_sha256':rec['input_checkpoint_sha256'],'output_checkpoint_state_sha256':rec['result']['checkpoint']['state_sha256'],
                         'previous_receipt_sha256':chain,'physics_audit_receipt':str(owner.OUT.parent/'independent_audit_01/results.json'),
                         'physics_audit_sha256':api.sha(owner.OUT.parent/'independent_audit_01/results.json'),
                         'audit_mode':'fresh exact trace extraction; prior independent raw physics audit reused by hash', 'design_sha256':api.sha(DESIGN)}
                marker=path.with_suffix('.audit.json');api.write(marker,receipt);chain=api.sha(marker)
                artifacts[str(path)]=api.sha(path);artifacts[str(marker)]=chain;entries.append(receipt);cp=rec['result']['checkpoint']
        cases[case]={'shape':info['shape'],'factor':info['factor'],'initial':initial.tolist(),'end_s':cp['state']['t'],'spec':spec,'entries':entries}
    def blocks(c):
        for e in c['entries']:
            api.require(api.sha(e['trace'])==e['trace_sha256'],'trace seal before streaming')
            arr=np.load(e['trace'],mmap_mode='r',allow_pickle=False);api.require(arr.shape==(e['rows'],13),'trace shape');yield arr
    results=[];reference=api.read(previous.OUT/'results.json')
    for shape in ['rigid_prolate_ar4','equal_volume_sphere']:
        a=next(x for x in cases.values() if x['shape']==shape and x['factor']==2.)
        b=next(x for x in cases.values() if x['shape']==shape and x['factor']==1.)
        cfg=b['spec']['config'];t=time.perf_counter()
        got=candidate.metrics(blocks(a),blocks(b),a['initial'],b['initial'],a['end_s'],b['end_s'],cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
        elapsed=time.perf_counter()-t;values={'pose_b':got['whole_position_over_b_max'],'axis':got['whole_axis_vector_norm_max'],
                'endpoint_velocity_U':got['endpoint_q_over_U_max'],'mean_L1_velocity_U':got['mean_L1_q_over_U_max']}
        expected=next(x for x in reference['comparisons'] if x['shape']==shape)
        api.require(all(np.isclose(v,expected['values'][k],rtol=d['oracle_rtol'],atol=d['oracle_atol']) for k,v in values.items()),'original real-path metric oracle')
        result={'shape':shape,'values':values,'passed':all(v<=d['limits'][k] for k,v in values.items()),'streaming_detail':got,'comparison_wall_s':elapsed}
        results.append(result);print('REAL_STREAM',shape,'seconds',elapsed,'working',got['working_set'],flush=True)
    verify(d);api.verify_mapping(artifacts)
    report={'passed':all(x['passed'] for x in results),'comparisons':results,'cases':cases,'artifacts':artifacts,'wall_s':time.perf_counter()-start,
            'trace_bytes':sum(Path(p).stat().st_size for p in artifacts if p.endswith('.npy')),'new_trajectory_steps':0,'design_sha256':api.sha(DESIGN),
            'production_ready':False,'claim':d['claim']}
    api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':report['passed'],'results_sha256':api.sha(OUT/'results.json')});print('REAL_STREAM_PASS',report['passed'],flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
