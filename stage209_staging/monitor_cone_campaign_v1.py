"""Read-only original seal monitor, explicit failed receipts and PID epochs."""
from pathlib import Path
import json,sys,os
SOURCE=Path(__file__).resolve().parents[1]/'stage200_staging/monitor_revised_campaign_v1.py'

def run(expected):
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):raise ValueError('exact frozen design SHA256 required')
    text=SOURCE.read_text();mapping={'stage200_runs/revised_deadline_campaign_20260927/run_01':'stage209_runs/cone_feasibility_campaign_20260930/run_01','stage200_designs/revised_deadline_campaign_20260927/design_01.json':'stage209_designs/cone_feasibility_campaign_20260930/design_01.json','8a973a1eee156023d00994f1476b06d69269300607b1cb2028af5bb3bfb9d923':expected,'Stage200':'Stage209'}
    for before,after in mapping.items():
        if before!='Stage200':assert text.count(before)==1,before
        text=text.replace(before,after)
    ns=dict(__name__='_stage209_read_only',__file__=__file__);exec(compile(text,__file__+'::unchanged_seal_checks','exec'),ns)
    r=ns['run']();d=ns['read'](ns['DESIGN']);root=ns['ROOT']
    if any(ns['sha'](p)!=h for p,h in d['inputs'].items()):raise RuntimeError('frozen input lineage changed')
    r['frozen_inputs_verified']=True;r['monitor_source_sha256']=ns['sha'](__file__)
    epochs={}
    launch=ns['read'](root/'launch.json');epochs[launch['supervisor_pid']]=launch['utc']
    for file in [root/'auditor_launch.json',*sorted(root.glob('dispatch_*.json'))]:
        if file.exists():
            item=ns['read'](file);epochs[item['pid']]=item['utc']
    for item in r['processes']:
        if not item.get('alive'):continue
        try:
            proc=ns['psutil'].Process(item['pid']);created=proc.create_time();started=ns['datetime'].fromisoformat(epochs[item['pid']]).timestamp()
            item['created']=created;item['creation_epoch_bound']=abs(created-started)<3.
            item['bound_active_identity']=item['command_bound'] and item['creation_epoch_bound']
        except ns['psutil'].NoSuchProcess:item['alive']=False
    failed=[]
    for path in root.rglob('segment_*.audit.json'):
        receipt=ns['read'](path)
        if receipt.get('status')!='independently_verified':failed.append(dict(path=str(path),case=receipt.get('case'),segment=receipt.get('segment'),status=receipt.get('status'),error=receipt.get('error')))
    r['failed_receipts']=failed;r['failure_markers']+= [x['path'] for x in failed]
    r['terminal_evaluators']=[]
    evaluator=str(Path(__file__).with_name('cone_feasibility_campaign_v1.py'))
    for proc in ns['psutil'].process_iter(['name']):
        if 'python' not in (proc.info['name'] or '').lower():continue
        try:
            argv=proc.cmdline()
            if argv[-3:]==[evaluator,'evaluate','campaign']:r['terminal_evaluators'].append(dict(pid=proc.pid,created=proc.create_time(),argv=argv,cpu_seconds=sum(proc.cpu_times()[:2])))
        except ns['psutil'].NoSuchProcess:continue
    return r
if __name__=='__main__':print(json.dumps(run(sys.argv[1]),indent=2))
