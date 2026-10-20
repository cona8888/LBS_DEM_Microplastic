"""Independent zero-step copy/receipt/trace/drain proof; no old preflight promotion."""
from pathlib import Path
import copy,hashlib,json,lzma,os,psutil,sys,traceback
import numpy as np
import qualify_isolated_fixtures_v1 as fixture
api,job=fixture.api,fixture.real
q=fixture.original.q
OUT=fixture.OUT.parent/'independent_01'

def run():
    fixture.authenticate();result=fixture.original.sealed(fixture.OUT/'results.json')
    api.verify_mapping(result['inputs']);api.require(result['passed'] and result['new_trajectory_steps']==0 and result['fixture_archives']==8,'complete zero-step fixture run')
    launch=api.read(fixture.RUN/'launch.json')
    api.require(not psutil.pid_exists(launch['pid']),'fixture runner retired before independent acceptance')
    api.require(not OUT.exists(),'exclusive independent fixture output');OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0})
    d=api.read(job.DESIGN);dsha=api.sha(job.DESIGN);reports=[];controls=[]
    try:
        with fixture.original.refs.reference.forbid_producer():
            job.parent.b.old.parent.configure()
            _,data,meta=api.fields.load(2,1.,6)
            geo=job.prior.candidate.original.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
            for label in ('cutoff_drain','failure_drain'):
                root=fixture.RUN/label/'live';isolated=fixture.isolated(root);isolated.verify(d)
                term=api.read(root/'auditor_complete.json')
                api.require(term['design_sha256']==dsha and len(term['items'])==4
                    and sum(x['passed'] for x in term['items'])==(4 if label=='cutoff_drain' else 2)
                    and term['passed']==(label=='cutoff_drain'),'all copied records drained; independent chain survives injected failure')
                lineage=api.read(root/'copy_lineage.json')
                api.require(len(lineage['copies'])==4 and lineage['new_trajectory_steps']==0,'exact copy-only inventory')
                for ci,case in enumerate(d['cases'][:2]):
                    prefix=source_prefix=None;hist=ref=None;before=prior_receipt=None;poisoned=False
                    for index in (1,2):
                        p=job.paths(root,case['id'],index);source=job.paths(job.root_for('preflight'),case['id'],index)
                        item=next(x for x in lineage['copies'] if x['copy']==str(p['raw']))
                        api.require(item['source']==str(source['raw']) and item['source_sha256']==api.sha(source['raw']),'hash-bound original source record')
                        seal=api.read(p['raw'].with_suffix('.seal.json'));packed=p['raw'].read_bytes();raw=lzma.decompress(packed)
                        api.require(hashlib.sha256(packed).hexdigest()==seal['compressed_sha256'] and hashlib.sha256(raw).hexdigest()==seal['uncompressed_sha256'] and len(raw)==seal['uncompressed_bytes'],'copied compressed/uncompressed seals')
                        independent=q.independent_file(p['raw'],dsha,hist,ref)
                        record,prefix=job.codec.read_record(p['raw'],dsha,prefix)
                        api.require(q.repair.base.raw_bytes(independent)==q.repair.base.raw_bytes(record),'independent copied full history decoder identity')
                        hist=independent['result']['history'];ref=prefix.reference()
                        original,source_prefix=job.codec.read_record(source['raw'],dsha,source_prefix)
                        expected=copy.deepcopy(original)
                        injected=(label=='failure_drain' and ci==0 and index==1)
                        if injected:expected['result']['checkpoint']['state_sha256']='0'*64
                        api.require(record==expected and item['injected_checkpoint_hash_failure']==injected,'only declared checkpoint-hash corruption; exact original rows and all fields')
                        receipt=api.read(p['receipt'])
                        if injected:
                            try:job.kernel.evaluate(record,case['spec'],job.binding(d,case),before,geo,dsha,d['minimum_gap_semantics'])
                            except (RuntimeError,AssertionError,ValueError):controls.append('injected_checkpoint_hash_independently_rejected')
                            else:raise AssertionError('injected bad checkpoint accepted')
                            poisoned=True
                        if poisoned:
                            api.require(receipt['status']=='audit_failed' and not p['trace'].exists(),'failed chain never receives accepted trace/receipt')
                            if index==2:api.require('unverified predecessor' in receipt['error'],'poisoned successor explicitly rejected')
                            summary=None
                        else:
                            job.policy.verify_receipt(p,case['id'],index,dsha,d['audit_source_sha256'],api.digest(before),prior_receipt)
                            summary=job.kernel.evaluate(record,case['spec'],job.binding(d,case),before,geo,dsha,d['minimum_gap_semantics'])
                            api.require(summary['passed'] and {k:v for k,v in summary.items() if k!='audit_seconds'}=={k:v for k,v in receipt['summary'].items() if k!='audit_seconds'},'full independent original physical gates')
                            trace=np.asarray([[x['time_s'],*x['position_m'],*x['orientation'],*x['velocity_generalized']] for x in record['rows']])
                            api.require(np.array_equal(trace,np.load(p['trace'],allow_pickle=False)),'complete copied trace identity')
                            before=record['result']['checkpoint'];prior_receipt=api.sha(p['receipt'])
                        reports.append({'path':str(p['raw']),'injected':injected,'accepted_copy_audit':not poisoned,'summary':summary,'new_trajectory_steps':0})
            api.require(len(reports)==8 and sum(x['accepted_copy_audit'] for x in reports)==6,'eight copies, six passing audits, two intentionally rejected copies')
            api.require(api.read(fixture.RUN/'exclusive.json')=={'fixture':True} and not (fixture.RUN/'pending_guard.json').exists()
                and len(list(fixture.RUN.glob('pending_guard.json.pending.*')))==1,'exclusive marker/pending controls retained')
            fixture.authenticate();api.verify_mapping(result['inputs'])
            failed=fixture.original.sealed(fixture.FAILED)
            inputs={str(p):api.sha(p) for p in fixture.RUN.rglob('*') if p.is_file()}
            for p in (fixture.WORK,fixture.BIND,fixture.FAILED,fixture.OUT/'results.json',fixture.OUT/'completion.json',Path(__file__),Path(fixture.__file__)):inputs[str(p)]=api.sha(p)
            r={'passed':True,'administrative_fixture_qualification_passed':True,'complementary_full_stack_qualification_passed':True,
                'stage216_original_preflight_passed':False,'stage216_failure_preserved':True,'new_trajectory_steps':0,
                'explicitly_reused_independently_passing_stage216_steps':17000,'separate_previous_saved_policy_steps':10600,'total_saved_policy_qualification_steps':27600,
                'new_fixture_copies':8,'fixture_reports':reports,'negative_controls':controls,'producer_classifier_never_called':True,
                'real_job_namespace_unchanged':True,'production_authorized':False,'campaign_launch_ready':False,'resource_deadline_fit_unverified':True,
                'failure_accounting_sha256':api.sha(fixture.FAILED),'inputs':inputs,'claim':'Original numerical/restart/parallel/live gates independently verified in failed Stage216; original drain assertions verified separately in new isolated administrative fixture. No old-run promotion, new trajectories, production or validation.'}
            job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
            print('INDEPENDENT_ISOLATED_FIXTURES_PASS',len(reports),flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':run()
