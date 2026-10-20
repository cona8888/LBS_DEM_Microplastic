"""Filesystem protocol units; synthetic fixtures, zero trajectory steps."""
from pathlib import Path
import copy,datetime,time
import bounded_live_audit_v1 as job
api=job.api
RUN=job.ROOT/'stage182_runs/bounded_live_audit_20260924/protocol_fixtures_01'
OUT=job.ROOT/'stage182_evaluations/bounded_live_audit_20260924/protocol_units_01'


def main():
    RUN.mkdir(exist_ok=False,parents=True);OUT.mkdir(exist_ok=False,parents=True);old_run,old_design=job.RUN,job.DESIGN
    guards=[];checks=[]
    def reject(label,fn):
        try:fn()
        except (RuntimeError,ValueError,FileNotFoundError,FileExistsError,KeyError):guards.append(label);return
        raise AssertionError('accepted invalid protocol '+label)
    try:
        job.RUN=RUN;job.DESIGN=RUN/'synthetic_design.json';job.commit(job.DESIGN,{'synthetic_protocol_fixture_only':True})
        raw=RUN/'synthetic.json.xz';seal=raw.with_suffix('.seal.json');trace=RUN/'synthetic_trace.json'
        for p in [raw,seal,trace]:job.commit(p,{'synthetic_protocol_fixture_only':True,'name':p.name})
        digest=api.sha(raw);reject('exclusive_commit',lambda:job.commit(raw,{}));api.require(api.sha(raw)==digest,'occupied file unchanged');checks.append('atomic_exclusive_commit')
        api.require(not list(RUN.glob('*.pending.*')),'no partial success markers');checks.append('no_partial_marker')
        paths={'raw':raw};c={'id':'synthetic_case'};before={'synthetic_checkpoint':True}
        marker={'case':c['id'],'segment':1,'design_sha256':api.sha(job.DESIGN),'raw_path':str(raw),'raw_sha256':api.sha(raw),'seal_sha256':api.sha(seal),'input_checkpoint_sha256':api.digest(before)}
        job.verify_ready(marker,paths,c,1,{},before);checks.append('ready_identity')
        for label,key,value in [('ready_wrong_case','case','other'),('ready_wrong_index','segment',2),('ready_wrong_design','design_sha256','0'*64),
                                 ('ready_wrong_path','raw_path',str(RUN/'unknown')),('ready_changed_raw','raw_sha256','0'*64),('ready_changed_seal','seal_sha256','0'*64),('ready_wrong_checkpoint','input_checkpoint_sha256','0'*64)]:
            bad=copy.deepcopy(marker);bad[key]=value;reject(label,lambda bad=bad:job.verify_ready(bad,paths,c,1,{},before))
        base={'status':'independently_verified','summary':{'passed':True},'design_sha256':api.sha(job.DESIGN),'audit_source_sha256':api.sha(job.kernel.__file__),
              'raw_sha256':api.sha(raw),'trace_path':str(trace),'trace_sha256':api.sha(trace)}
        def fixture(label,change=None):
            receipt_path=RUN/(label+'.audit.json');ready=RUN/(label+'.ready.json');job.commit(ready,marker);r=copy.deepcopy(base);r['ready_sha256']=api.sha(ready)
            if change:change(r)
            job.commit(receipt_path,r);return receipt_path
        api.require(job.acknowledged(fixture('good')),'valid audit acknowledgement');checks.append('valid_acknowledgement')
        api.require(job.acknowledged(RUN/'missing.audit.json') is False,'unwritten receipt applies back-pressure');checks.append('missing_receipt_waits')
        for label,key,value in [('failed_audit','summary',{'passed':False}),('wrong_status','status','completed'),('wrong_audit_design','design_sha256','0'*64),
                                 ('wrong_auditor','audit_source_sha256','0'*64),('wrong_ready_hash','ready_sha256','0'*64),('wrong_raw_hash','raw_sha256','0'*64),('wrong_trace_hash','trace_sha256','0'*64)]:
            path=fixture(label,lambda r,key=key,value=value:r.update({key:value}));reject(label,lambda path=path:job.acknowledged(path))
        future=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)).isoformat();d={'stop_utc':future}
        api.require(not job.stopped(d),'no stop without reason');checks.append('normal_dispatch_allowed')
        api.require(job.stopped({'stop_utc':'2000-01-01T00:00:00Z'}),'expired cutoff stop');checks.append('deadline_stop')
        failure_run=RUN/'failure_case';failure_run.mkdir();job.RUN=failure_run;job.commit(failure_run/'failure.json',{'synthetic':True})
        api.require(job.stopped(d),'failure latch stops dispatch');checks.append('failure_latch')
        stop_run=RUN/'stop_case';stop_run.mkdir();job.RUN=stop_run;job.commit(stop_run/'stop_requested.json',{'synthetic':True})
        api.require(job.stopped(d),'cooperative marker stops dispatch');checks.append('cooperative_stop_latch')
        report={'passed':True,'checks':checks,'rejected_invalid_protocols':guards,'new_trajectory_steps':0,
            'sources':{str(Path(p).resolve()):api.sha(p) for p in [__file__,job.__file__]},'artifacts':{str(p):api.sha(p) for p in RUN.rglob('*') if p.is_file()},
            'claim':'Synthetic commit, acknowledgement and stop protocol units only; no simulated outputs.'}
        api.write(OUT/'results.json',report);api.write(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('PROTOCOL_PASS',len(checks),len(guards),flush=True)
    finally:job.RUN,job.DESIGN=old_run,old_design


if __name__=='__main__':main()
