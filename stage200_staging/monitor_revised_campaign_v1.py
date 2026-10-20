"""Read-only monitoring of the one immutable Stage200 campaign."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,sys,psutil
ROOT=Path('D:/MATDEM_MICROPLASTIC/stage200_runs/revised_deadline_campaign_20260927/run_01')
DESIGN=Path('C:/MATDEM_MICROPLASTIC/stage200_designs/revised_deadline_campaign_20260927/design_01.json')
EXPECTED='8a973a1eee156023d00994f1476b06d69269300607b1cb2028af5bb3bfb9d923'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def run():
    if sha(DESIGN)!=EXPECTED:raise RuntimeError('frozen Stage200 design changed')
    d=read(DESIGN);now=datetime.now(timezone.utc)
    changed_sources=[p for p,h in d['sources'].items() if sha(p)!=h]
    if changed_sources:raise RuntimeError('frozen sources changed: '+repr(changed_sources))
    launch=read(ROOT/'launch.json');assert launch['design_sha256']==EXPECTED
    bound=[('supervisor',launch['supervisor_pid'],launch['argv'])]
    if (ROOT/'auditor_launch.json').exists():
        x=read(ROOT/'auditor_launch.json');assert x['design_sha256']==EXPECTED;bound.append(('auditor',x['pid'],x['argv']))
    for p in sorted(ROOT.glob('dispatch_*.json')):
        x=read(p);assert x['design_sha256']==EXPECTED;bound.append((x['case'],x['pid'],x['argv']))
    processes=[]
    for role,pid,argv in bound:
        try:
            p=psutil.Process(pid);cmd=p.cmdline();expected=[str(v).lower() for v in argv]
            match=[str(v).lower() for v in cmd][-len(expected):]==expected
            processes.append(dict(role=role,pid=pid,alive=True,command_bound=match,argv=cmd,cpu_seconds=sum(p.cpu_times()[:2]),rss_bytes=p.memory_info().rss,affinity=p.cpu_affinity()))
        except psutil.NoSuchProcess:processes.append(dict(role=role,pid=pid,alive=False))
    cases=[];outstanding=0
    for c in d['cases']:
        folder=ROOT/c['id'];ready=sorted(folder.glob('segment_*.ready.json'));receipts=sorted(folder.glob('segment_*.audit.json'))
        saved=sum(read(p)['steps'] for p in ready);valid=[read(p) for p in receipts];ok=[x for x in valid if x.get('status')=='independently_verified']
        outstanding+=len(ready)-len(ok);tail=ok[-1] if ok else None
        tail_verified=None
        if tail:
            index=tail['segment'];stem=f'segment_{index:05d}';raw=folder/(stem+'.json.xz');marker=folder/(stem+'.ready.json');m=read(marker);seal=raw.with_suffix('.seal.json')
            tail_verified=(sha(raw)==tail['raw_sha256']==m['raw_sha256'] and sha(marker)==tail['ready_sha256'] and sha(seal)==m['seal_sha256'] and tail['design_sha256']==EXPECTED)
            if not tail_verified:raise RuntimeError('latest receipt/raw/seal binding failed '+c['id'])
        cases.append(dict(case=c['id'],dispatched=folder.exists(),sealed_segments=len(ready),verified_segments=len(ok),declared_saved_steps=saved,last_verified_time_s=None if tail is None else tail['summary']['stop_s'],horizon_s=c['spec']['horizon_s'],last_verified_status=None if tail is None else tail['summary']['status'],complete_observation=False if tail is None else tail['summary']['complete_observation'],latest_raw_seal_verified=tail_verified,producer_retired=(folder/'completion.json').exists()))
    # Read-only samples may straddle concurrent publications: recheck an apparent
    # backlog discrepancy on a later snapshot rather than mutate/terminate work.
    errors=[str(p) for p in ROOT.rglob('*.failure.json')]+[str(p) for p in ROOT.rglob('*.exception.json')]
    stderr=[dict(path=str(p),bytes=p.stat().st_size,tail=p.read_text(encoding='utf-8',errors='replace')[-2000:]) for p in ROOT.glob('*.stderr.log') if p.stat().st_size]
    start=datetime.fromisoformat(launch['utc']);cutoff=datetime.fromisoformat(d['simulation_cutoff_utc']);planning_end=start+__import__('datetime').timedelta(hours=d['resource_scenario']['hours_with_margin'])
    return dict(utc=now.isoformat(),design_sha256=EXPECTED,frozen_sources_verified=True,processes=processes,cases=cases,outstanding_snapshot=outstanding,declared_global_bound=6,failure_markers=errors,stderr=stderr,stop_requested=read(ROOT/'stop_requested.json') if (ROOT/'stop_requested.json').exists() else None,terminal=read(ROOT/'completion.json') if (ROOT/'completion.json').exists() else None,free_bytes=shutil.disk_usage(ROOT).free,reserve_bytes=d['budget']['minimum_free_disk_bytes'],simulation_cutoff_utc=d['simulation_cutoff_utc'],final_audit_deadline_utc=d['final_audit_deadline_utc'],remaining_simulation_hours=(cutoff-now).total_seconds()/3600,initial_measured_regime_planning_finish_utc=planning_end.isoformat(),forecast_is_not_completion_guarantee=True)
if __name__=='__main__':print(json.dumps(run(),indent=2))
