"""Diagnostic-only fallback recording: zero-step algebra and 6,500 steps.

Six 1,000-step optimized archived controls, plus a 500-step already-qualified
legacy fallback window. Every new trace and full state must match its oracle.
"""
from pathlib import Path
from types import SimpleNamespace
import copy,datetime,os,shutil,sys,time,traceback
import numpy as np
import capture_fallback_systems_v1 as capture
import audit_fallback_systems_v1 as physical
import audit_optimized_record_v2 as kernel
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage181_staging'),str(ROOT/'stage182_staging'),str(ROOT/'stage172_staging')]
import qualify_runtime_deadline_v1 as previous
import bounded_live_audit_v1 as live
import qualify_fast_contact_v1 as units
api,parent,fast=previous.api,previous.parent,previous.fast
prior,codec=previous.prior,previous.codec
DESIGN=ROOT/'stage183_designs/fallback_evidence_20260924/design_01.json'
RUN=ROOT/'stage183_runs/fallback_evidence_20260924/qualification_01'
OUT=ROOT/'stage183_evaluations/fallback_evidence_20260924/qualification_01'


def prepare():
    live.verify(api.read(live.DESIGN));live_result=api.read(live.OUT/'results.json');api.require(live_result['passed'] and live_result['new_steps']==36000,'live audit prerequisite')
    matrices=api.read(units.DESIGN)['matrices'];cases=[];inputs=[units.DESIGN,live.DESIGN,live.OUT/'results.json',live.OUT/'completion.json',previous.DESIGN]
    for c in api.read(previous.DESIGN)['cases']:
        cases.append({**c,'mode':'optimized','raw_design_sha256':api.sha(prior.DESIGN),'steps':1000})
    old=units.p;source=old.RUN/'factor_1.0/segment_006.json.gz';oracle=source.with_name('segment_007.json.gz')
    cases.append({'id':'legacy_active_fallback','mode':'legacy','source':str(source),'oracle':str(oracle),
        'raw_design_sha256':api.sha(old.DESIGN),'steps':500,'spec':parent.storage.read_record(source,api.sha(old.DESIGN))['spec']})
    for c in cases:
        for key in ['source','oracle']:
            p=Path(c[key]);inputs.extend([p,p.with_suffix('.seal.json')])
    inputs.extend(Path(p) for p in matrices);d={'stage':'Stage183 fallback evidence qualification','cases':cases,'matrices':matrices,
        'physical_changes':[],'maximum_new_steps':6500,'prior_work_steps':243175,'work_step_ceiling':250000,'wall_seconds':900,
        'stop_utc':'2026-09-24T02:46:55+00:00','sources':parent.source_map(),'inputs':{str(p):api.sha(p) for p in inputs},
        'minimum_gap_semantics':api.read(prior.DESIGN)['minimum_gap_semantics'],'audit_extension':kernel.STRUCTURAL_IDENTITY,
        'claim':'Read-only fallback system recording and independent balance/force audit. Exact existing trajectories required; no new model or production launch.'}
    api.require(d['prior_work_steps']+d['maximum_new_steps']<=d['work_step_ceiling'],'four-hour step budget')
    d['binding']=api.digest(d);DESIGN.parent.mkdir(exist_ok=True,parents=True);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'self binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);live.verify(api.read(live.DESIGN));units.verify(api.read(units.DESIGN))
    api.require(d['audit_extension']==kernel.STRUCTURAL_IDENTITY,'exact frozen audit extension')


def unit_checks(d):
    reports=[];rejected=[];runtime=parent.engine.runtime;original=runtime.mixed.solve;last=None
    with prior.p.hot.scope(),parent.fix.scope(),fast.old.scope(runtime,True):
        for path in d['matrices']:
            r=api.read(path);v,M,J,g=[np.asarray(r[k]) for k in ['vfree','mobility','jacobian','gaps']]
            if len(g)!=3:continue
            args=(v,M,J,g,r['dt'],r['friction'],1e-10,25000)
            try:expected=runtime.mixed.solve(*args)
            except (RuntimeError,ValueError,np.linalg.LinAlgError):rejected.append(path);continue
            capture.records.clear()
            with capture.scope(runtime,True):got=runtime.mixed.solve(*args)
            api.require(np.array_equal(expected[0],got[0]),'diagnostic observer leaves velocity exact')
            # Health may carry wall timing of a roundoff certificate; all physics
            # fields apart from that diagnostic duration must remain identical.
            trim=lambda h:{k:v for k,v in h.items() if k!='certificate_seconds'}
            api.require(trim(expected[1])==trim(got[1]) and len(capture.records)==1,'unchanged health and one system per solve')
            last=copy.deepcopy(capture.records[0]);audit=physical.physical(last);reports.append({'source':path,'exact_velocity':True,'exact_physical_health':True,'audit':audit})
    api.require(runtime.mixed.solve is original and reports,'observer scope restored')
    guards=[]
    for name,edit in [('bad_velocity',lambda x:x['velocity'].__setitem__(0,x['velocity'][0]+1e-3)),
        ('bad_force',lambda x:x['health']['reactions'].__setitem__(0,-1.)),('bad_gap',lambda x:x['gaps_m'].__setitem__(0,-1.)),
        ('bad_dt',lambda x:x.update(dt_s=0)),('nan_matrix',lambda x:x['mobility'][0].__setitem__(0,float('nan'))),('rejected_solve',lambda x:x.update(accepted=False))]:
        bad=copy.deepcopy(last);edit(bad)
        try:physical.physical(bad)
        except (RuntimeError,ValueError,np.linalg.LinAlgError):guards.append(name)
        else:raise AssertionError('force audit accepted '+name)
    # The observer must propagate the identical exception object and restore.
    failure=RuntimeError('synthetic diagnostic failure');mock=SimpleNamespace(mixed=SimpleNamespace())
    def fail(*args):raise failure
    mock.mixed.solve=fail;capture.records.clear()
    try:
        with capture.scope(mock,True):mock.mixed.solve(*args)
    except RuntimeError as error:api.require(error is failure,'original failure identity')
    api.require(mock.mixed.solve is fail and len(capture.records)==1 and capture.records[0]['accepted'] is False,'failed solve recorded without retry')
    capture.records.clear();fast.old.telemetry.clear();parent.fix.telemetry.clear();parent.model.calls.clear();fast.attempts.clear();fast.telemetry.clear();prior.candidate.records.clear()
    return {'passed':True,'matrix_reports':reports,'reference_rejections_preserved':rejected,'invalid_systems_rejected':guards,'failure_propagation_and_restoration':True,'new_trajectory_steps':0}


def run():
    d=api.read(DESIGN);verify(d);api.require(time.time()<previous.candidate.parse_deadline(d['stop_utc'])-120,'bounded work reserve')
    RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);start=time.perf_counter();total=0;results=[];artifacts={}
    api.write(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'design_sha256':api.sha(DESIGN),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    try:
        parent.b.old.parent.configure();fast.capture_systems=True;units_result=unit_checks(d);api.write(OUT/'units.json',units_result,raw=True)
        with prior.snapshot.scope(api,d['cases'][0]['spec']['field_metadata']):
            field,data,meta=api.fields.load(2,1.,6);geometry=prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            for c in d['cases']:
                api.require(time.perf_counter()-start<d['wall_seconds'] and time.time()<previous.candidate.parse_deadline(d['stop_utc'])-120,'bounded work clock')
                api.require(shutil.disk_usage(ROOT).free>20*1024**3+codec.base.MAX_COMPRESSED,'disk reserve')
                reader=prior.independent.independent_read if hasattr(prior,'independent') else previous.independent.independent_read
                if c['mode']=='legacy':reader=parent.storage.read_record
                source=reader(Path(c['source']),c['raw_design_sha256']);oracle=reader(Path(c['oracle']),c['raw_design_sha256'])
                binding=api.digest([d['binding'],c['id']]);cp=parent.model.checkpoint(c['spec'],binding,source['result']['checkpoint'],True);before=copy.deepcopy(cp);t=time.perf_counter()
                solver=previous.candidate.scope(parent.engine.runtime,d['stop_utc'],True) if c['mode']=='optimized' else fast.old.scope(parent.engine.runtime,True)
                with prior.p.hot.scope(),parent.storage.step_budget_scope(20_000_000),parent.fix.scope(),solver,capture.scope(parent.engine.runtime,True),prior.candidate.scope():
                    result,rows=parent.engine.runtime.execute(c['spec'],binding,checkpoint=cp,pause=cp['state']['steps']+c['steps'])
                record={'spec':c['spec'],'result':result,'rows':rows,'input_checkpoint_sha256':api.digest(before),'effective_binding':parent.model.binding_for(binding,True),
                    'design_sha256':api.sha(DESIGN),'step_cap':c['steps'],'compute_call_wall_s':time.perf_counter()-t,
                    'early_attempts':copy.deepcopy(fast.attempts),'repairs':copy.deepcopy(fast.old.telemetry),'backend_calls':copy.deepcopy(parent.model.calls),
                    'certificates':copy.deepcopy(parent.fix.telemetry),'sweep_certificates':copy.deepcopy(prior.candidate.records),
                    'fallback_systems':copy.deepcopy(capture.records),'minimum_gap_semantics':d['minimum_gap_semantics']}
                path=RUN/(c['id']+'.json.xz');codec.write_record(path,record);total+=len(rows)
                api.require(total<=d['maximum_new_steps'] and len(rows)==c['steps'],'work step accounting')
                api.require(rows==oracle['rows'] and result['checkpoint']['state']==oracle['result']['checkpoint']['state'],'exact archived trace/full-state identity')
                decoded,_=codec.read_record(path,api.sha(DESIGN));summary=kernel.evaluate(decoded,c['spec'],binding,before,geometry,api.sha(DESIGN),d['minimum_gap_semantics'])
                if c['mode']=='legacy':api.require(summary['fallback_force_systems']==c['steps'],'all 500 active fallback systems independently audited')
                results.append({'case':c['id'],'mode':c['mode'],'exact_trace_and_state':True,'audit':summary,'path':str(path)})
                for p in [path,path.with_suffix('.seal.json')]:artifacts[str(p)]=api.sha(p)
                capture.records.clear();fast.attempts.clear();fast.telemetry.clear();fast.old.telemetry.clear();parent.fix.telemetry.clear();parent.model.calls.clear();prior.candidate.records.clear()
                print('CAPTURE_IDENTITY',c['id'],len(rows),'fallbacks',summary['fallback_force_systems'],flush=True)
        verify(d);api.verify_mapping(artifacts);report={'passed':True,'new_steps':total,'work_cumulative_steps':total+d['prior_work_steps'],'cases':results,
            'artifacts':artifacts,'units_sha256':api.sha(OUT/'units.json'),'design_sha256':api.sha(DESIGN),'wall_seconds':time.perf_counter()-start,
            'claim':d['claim'],'campaign_launched':False,'full_path_qualified':False}
        api.write(OUT/'results.json',report,raw=True);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('FALLBACK_CAPTURE_PASS',total,flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_steps':total});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
