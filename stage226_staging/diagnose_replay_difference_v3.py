"""Preserve both routes of the first strict mismatch; no acceptance relaxation."""
from pathlib import Path
import sys, traceback
import replay_common_v1 as c
import replay_exhausted_failure_v3 as r
import psutil
OUT=c.OUT/'difference_diagnosis_03'


def differences(a,b,path='health'):
    if isinstance(a,dict) and isinstance(b,dict):
        rows=[]
        for k in sorted(set(a)|set(b)):
            if k not in a or k not in b:rows.append(dict(path=path+'.'+k,actual=a.get(k),expected=b.get(k)))
            else:rows+=differences(a[k],b[k],path+'.'+k)
        return rows
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        return [v for i,(x,y) in enumerate(zip(a,b)) for v in differences(x,y,f'{path}[{i}]')]
    return [] if a==b else [dict(path=path,actual=a,expected=b)]


def run():
    auth=c.bound();c.environment();d=c.read(r.DESIGN);c.verify(d['sources']);c.verify(d['inputs'])
    failure=c.read(r.OUT/'failure.json')
    assert failure['outer_calls_attempted']==len(failure['completed'])+1
    inventory=c.read(r.FIXTURE_DIR/'fixtures.json');row=inventory['fixtures'][len(failure['completed'])//2]
    c.commit(OUT/'design.json',dict(utc=c.utc(),authorization_sha256=c.sha(c.AUTH),new_trajectory_steps=0,
        maximum_outer_calls=2,sources={str(Path(__file__).resolve()):c.sha(__file__)},
        inputs={str(p):c.sha(p) for p in (r.DESIGN,r.OUT/'failure.json',r.FIXTURE_DIR/'fixtures.json')},
        fixture_id=row['fixture_id'],purpose='Observe strict mismatch; never promote either result or change a gate.'))
    psutil.Process().cpu_affinity([auth['logical_cpu']]);r.JOB.parent.b.old.parent.configure();r.STACK.candidate.warm()
    summaries=[]
    for mode in ('original','reuse'):
        c.bound()
        try:
            result=r.call(inventory,row,mode,auth['end_utc'])
        except Exception as error:
            tb=error.__traceback__;frame=None
            while tb:
                if tb.tb_frame.f_code is r.call.__code__:frame=tb.tb_frame.f_locals
                tb=tb.tb_next
            assert frame and 'answer' in frame and 'fixture' in frame,'Diagnostic failure must preserve executed force output'
            answer=r.plain(frame['answer']);fixture=r.plain(frame['fixture']);memo=r.plain(frame['memo'])
            association=r.ASSOCIATION.evaluate(fixture,row['force_audit_before'])
            result=dict(strict_original_comparison_passed=False,error=repr(error),traceback=traceback.format_exc(),
                actual_velocity=answer[0],actual_health=answer[1],force_audit_fixture=fixture,reuse_log=memo,
                physical_association_audit=association,
                scientific_differences=differences(r.scientific(answer[1]),r.scientific(row['expected_outer_outputs']['health'])))
        else:result.update(strict_original_comparison_passed=True,scientific_differences=[])
        c.commit(OUT/(mode+'.json'),result)
        summary=dict(mode=mode,differences=result['scientific_differences'],strict_original_comparison_passed=result['strict_original_comparison_passed'],
                     artifacts_sha256=c.sha(OUT/(mode+'.json')))
        summaries.append(summary);print(mode,summary['differences'],flush=True)
    c.bound()
    c.commit(OUT/'results.json',dict(passed=True,diagnosis_only=True,new_trajectory_steps=0,outer_calls=2,
        utc=c.utc(),reports=summaries,production_authorized=False,prior_attempt_remains_failed=True,
        artifacts={str(p):c.sha(p) for p in OUT.glob('*.json')}))
    c.commit(OUT/'completion.json',dict(passed=True,results_sha256=c.sha(OUT/'results.json')))


if __name__=='__main__':run()
