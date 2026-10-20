"""Compare already-audited conditional paths; no integration or new physics."""
from pathlib import Path
import copy,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage177_staging'))
import extended_optimized_preflight_v1 as latest
import audit_extended_preflight_v1 as latest_audit
from audit_repaired_preflight_v1 import exact_l1
api,parent=latest.api,latest.parent
fibre=latest.prior.previous
sphere=fibre.unit.upstream.prior
DESIGN=ROOT/'stage178_designs/resource_readiness_20260924/conditional_trace_design_01.json'
OUT=ROOT/'stage178_evaluations/resource_readiness_20260924/conditional_paths_01'


def prepare():
    evidence=[latest_audit.OUT,fibre.OUT.parent/'independent_audit_01',sphere.OUT.parent/'independent_audit_01',latest.prior.OUT.parent/'independent_audit_01']
    inputs=[latest.DESIGN,latest.prior.DESIGN,fibre.DESIGN,sphere.DESIGN]
    for folder in evidence:
        r=api.read(folder/'results.json');api.require(r['integration_verified'],'audited predecessor')
        api.require(api.read(folder/'completion.json')['results_sha256']==api.sha(folder/'results.json'),'predecessor completion seal')
        inputs.extend([folder/'results.json',folder/'completion.json'])
    paths={}
    for shape,module,word in [('rigid_prolate_ar4',fibre,'fibre'),('equal_volume_sphere',sphere,'sphere')]:
        for factor in [1.,2.]:
            case=f's2_i0_{word}_f0p'+('03125' if factor==1 else '0625')
            root=module.RUN/f'factor_{factor}'
            if word=='fibre':root=root/'certificate'
            old=sorted(root.glob('segment_*.json.gz'));middle=sorted((latest.prior.RUN/case).glob('segment_*.json.gz'));new=sorted((latest.RUN/case).glob('segment_*.json.xz'))
            paths[case]={'shape':shape,'factor':factor,'initial':[str(p) for p in old],'middle':[str(p) for p in middle],'latest':[str(p) for p in new]}
            for p in old+middle+new:inputs.extend([p,p.with_suffix('.seal.json')])
    d={'stage':'Stage178 conditional comparison','physical_changes':[],'new_trajectory_steps':0,'cases':paths,
       'limits':api.read(sphere.DESIGN)['limits'],'reference_factor_relative_to_old_fine':1.,'selected_factor_relative_to_old_fine':2.,
       'sources':{str(Path(__file__).resolve()):api.sha(__file__),str(Path(latest_audit.stream_audit.__file__).resolve()):api.sha(latest_audit.stream_audit.__file__)},
       'inputs':{str(p):api.sha(p) for p in inputs},'convention':'Common interval from the original shared conditional state to the earlier available endpoint, without extrapolation, event alignment or smoothing.',
       'claim':'Extended selected-versus-fine conditional comparison only. No fresh full path, population release, empirical validation or new three-level convergence claim.'}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(exist_ok=True,parents=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])


def path_data(case,info):
    module=fibre if info['shape']=='rigid_prolate_ar4' else sphere;sd=api.read(module.DESIGN)
    if module is fibre:spec,binding,cp=module.setup(sd,info['factor'],'certificate')
    else:spec,binding,cp=module.p.setup(sd,info['factor'])
    seed=copy.deepcopy(cp);rows=[];states=[copy.deepcopy(seed['state'])]
    for phase,owner in [('initial',module),('middle',latest.prior),('latest',latest)]:
        if phase!='initial':
            dd=api.read(owner.DESIGN);c=next(x for x in dd['cases'] if x['id']==case)
            api.require(c['initial_checkpoint_state_sha256']==cp['state_sha256'],'exact cross-stage physical state link')
            spec=c['spec'];binding=api.digest([dd['binding'],case]);cp=parent.model.checkpoint(spec,binding,cp,True)
        for name in info[phase]:
            path=Path(name);rec=latest_audit.independent_read(path,api.sha(owner.DESIGN)) if phase=='latest' else parent.storage.read_record(path,api.sha(owner.DESIGN))
            api.require(rec['input_checkpoint_sha256']==api.digest(cp) and rec['spec']==spec,'complete sealed path chain')
            api.require(rec['result']['checkpoint']['state_sha256']==api.digest(rec['result']['checkpoint']['state']),'state SHA')
            t=cp['state']['t']
            for row in rec['rows']:
                api.require(t+row['dt_s']==row['time_s'],'unbroken physical clock');t=row['time_s']
            rows.extend(rec['rows']);cp=rec['result']['checkpoint']
    api.require(rows[-1]['time_s']==cp['state']['t'],'endpoint clock')
    array=np.array([[seed['state']['t'],*seed['state']['x'],*seed['state']['p'],*seed['state']['q']]]+
                   [[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rows],float)
    return {'spec':spec,'seed':seed,'rows':rows,'array':array,'end':cp}


def main():
    d=api.read(DESIGN);verify(d);OUT.mkdir(exist_ok=False,parents=True);results=[]
    for shape in ['rigid_prolate_ar4','equal_volume_sphere']:
        entries=[(k,v) for k,v in d['cases'].items() if v['shape']==shape];data={v['factor']:path_data(k,v) for k,v in entries}
        coarse,fine=data[2.],data[1.]
        api.require(coarse['seed']['state']==fine['seed']['state'],'same complete initial conditional state')
        start=fine['seed']['state']['t'];stop=min(coarse['end']['state']['t'],fine['end']['state']['t']);cfg=fine['spec']['config'];b=cfg['prolate_semiaxes_m'][1];U=cfg['target_mean_interstitial_velocity_m_s']
        arrays=[x['array'].copy() for x in [coarse,fine]]
        for arr in arrays:arr[:,0]-=start
        measured=latest_audit.stream_audit.metrics(*arrays,b,U,chunk=7000)
        l1=exact_l1(coarse['rows'],fine['rows'],start,stop,U)
        api.require(np.isclose(l1,measured['mean_L1_q_over_U_max'],rtol=1e-10,atol=1e-15),'independent interval L1 oracle')
        values={'pose_b':measured['whole_position_over_b_max'],'axis':measured['whole_axis_vector_norm_max'],
                'endpoint_velocity_U':measured['endpoint_q_over_U_max'],'mean_L1_velocity_U':l1}
        results.append({'shape':shape,'start_s':start,'common_stop_s':stop,'duration_s':stop-start,'values':values,'passed':all(v<=d['limits'][k] for k,v in values.items()),
                        'selected_steps':len(coarse['rows']),'fine_steps':len(fine['rows']),'endpoint_convention':measured['endpoint_convention']})
        print('CONDITIONAL',shape,results[-1],flush=True)
    verdict=all(x['passed'] for x in results);report={'passed':verdict,'comparisons':results,'limits':d['limits'],'new_trajectory_steps':0,
        'design_sha256':api.sha(DESIGN),'claim':d['claim'],'full_path_qualified':False,'campaign_launched':False}
    verify(d);api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':verdict,'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:main()
    else:raise ValueError('prepare | run')
