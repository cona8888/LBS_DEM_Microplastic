"""Witness the frozen terminal evaluator: exclusive launch, logs and exit code.

No evaluator equation, decoder, gate or raw artifact is changed. The witness
prevents duplicate audits and retains infrastructure failures that were missing
from the old interrupted terminal evaluation.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,os,subprocess,sys,time,traceback,psutil
import save_monitor_snapshot_v1 as io

ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/'stage203_designs/autonomous_completion_20260929/design_01.json'
SCRIPT=Path(__file__).with_name('autonomous_completion_campaign_v1.py')
BASE=ROOT/'stage203_evaluations/autonomous_completion_20260929'
WORK=BASE/'terminal_evaluator_01'
EVAL=BASE/'evaluation_01'
RUN=Path('D:/MATDEM_MICROPLASTIC/stage203_runs/autonomous_completion_20260929/run_01')
EXPECTED='6aa736ee9eb0e2ba797045086798aa0564d98446f896b8c3d56fc5223a4baa37'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return io.monitor.ns['sha'](path)
def utc():return datetime.now(timezone.utc)


def existing_evaluator():
    live=[]
    for p in psutil.process_iter(['pid','name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:
            argv=p.cmdline();tokens=[os.path.normcase(os.path.normpath(x)) for x in argv]
            if (tokens[-3:]==[os.path.normcase(str(SCRIPT)),'evaluate','campaign'] or os.path.normcase(str(Path(__file__).resolve())) in tokens):
                live.append(dict(pid=p.pid,argv=argv,created=p.create_time()))
        except psutil.NoSuchProcess:continue
    return live


def run():
    if sha(DESIGN)!=EXPECTED:raise RuntimeError('frozen design identity')
    d=read(DESIGN);terminal=read(RUN/'completion.json')
    if terminal['design_sha256']!=EXPECTED or not terminal['all_owned_processes_retired']:raise RuntimeError('terminal lifecycle not complete')
    if EVAL.exists() or WORK.exists() or existing_evaluator():raise RuntimeError('existing audit/output; never duplicate')
    if utc()>=datetime.fromisoformat(d['final_audit_deadline_utc']):raise RuntimeError('no new audit after cutoff')
    for mapping in (d['sources'],d['inputs']):
        if any(sha(p)!=h for p,h in mapping.items()):raise RuntimeError('immutable lineage changed')
    WORK.mkdir(parents=True,exist_ok=False)
    io.commit(WORK/'witness_launch.json',dict(pid=os.getpid(),argv=sys.argv,utc=utc().isoformat(),design_sha256=EXPECTED,source_sha256=sha(__file__),new_trajectory_steps=0))
    argv=[sys.executable,'-B','-u',str(SCRIPT),'evaluate','campaign']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',OMP_NUM_THREADS='1')
    try:
        with (WORK/'stdout.log').open('xb') as out,(WORK/'stderr.log').open('xb') as err:
            process=subprocess.Popen(argv,cwd=str(ROOT),env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        io.commit(WORK/'evaluator_launch.json',dict(pid=process.pid,argv=argv,created=psutil.Process(process.pid).create_time(),utc=utc().isoformat(),design_sha256=EXPECTED,source_sha256=sha(SCRIPT),threads=1,new_trajectory_steps=0))
        while process.poll() is None:
            if utc()>=datetime.fromisoformat(d['final_audit_deadline_utc']):
                io.commit(WORK/'unfinished_at_cutoff.json',dict(pid=process.pid,utc=utc().isoformat(),child_left_running=True,new_trajectory_steps=0));return
            time.sleep(5)
        result=dict(exit_code=process.returncode,utc=utc().isoformat(),design_sha256=EXPECTED,new_trajectory_steps=0,evaluation_output_exists=EVAL.exists())
        if (EVAL/'results.json').exists() and (EVAL/'completion.json').exists():
            seal=read(EVAL/'completion.json')
            if seal['results_sha256']!=sha(EVAL/'results.json'):raise RuntimeError('terminal evaluation completion seal')
            result.update(results_sha256=seal['results_sha256'],audit_passed=bool(seal['passed']))
        io.commit(WORK/'exit.json',result)
        io.commit(WORK/'completion.json',dict(passed=process.returncode==0 and 'results_sha256' in result,exit_sha256=sha(WORK/'exit.json'),audit_passed=result.get('audit_passed',False)))
        print('TERMINAL_EVALUATOR_EXIT',json.dumps(result),flush=True)
    except Exception as error:
        io.commit(WORK/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),utc=utc().isoformat(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
