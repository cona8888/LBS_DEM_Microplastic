"""Read-only Stage205 monitor; original scoped seal/receipt checks retained."""
from pathlib import Path
import hashlib,json,os
source=Path(__file__).resolve().parents[1]/'stage200_staging/monitor_revised_campaign_v1.py'
text=source.read_text(encoding='utf-8')
replacements={
    'stage200_runs/revised_deadline_campaign_20260927/run_01':'stage205_runs/receipt_repaired_campaign_20260930/run_01',
    'stage200_designs/revised_deadline_campaign_20260927/design_01.json':'stage205_designs/receipt_repaired_campaign_20260930/design_01.json',
    '8a973a1eee156023d00994f1476b06d69269300607b1cb2028af5bb3bfb9d923':'ffbef471714acf5ee16287aeb76eff97319480db23b135c17d798254ee870190',
    'Stage200':'Stage205',
}
for before,after in replacements.items():
    if before!='Stage200':assert text.count(before)==1,before
    text=text.replace(before,after)
ns=dict(__name__='_stage205_read_only_monitor',__file__=__file__)
exec(compile(text,__file__+'::same_seal_checks','exec'),ns)


def run():
    r=ns['run']();d=ns['read'](ns['DESIGN'])
    bad=[p for p,h in d['inputs'].items() if ns['sha'](p)!=h]
    if bad:raise RuntimeError('frozen input changed: '+repr(bad))
    r['frozen_inputs_verified']=True
    r['monitor_source_sha256']=ns['sha'](__file__)
    r['terminal_evaluators']=[]
    for p in ns['psutil'].process_iter(['pid','name']):
        if 'python' not in (p.info['name'] or '').lower():continue
        try:
            argv=p.cmdline();tail=[os.path.normcase(os.path.normpath(x)) for x in argv[-3:]]
            expected=[os.path.normcase(str(Path(__file__).with_name('receipt_repaired_campaign_v2.py'))),'evaluate','campaign']
            if tail==expected:r['terminal_evaluators'].append(dict(pid=p.pid,argv=argv,created=p.create_time(),cpu_seconds=sum(p.cpu_times()[:2])))
        except ns['psutil'].NoSuchProcess:continue
    return r


if __name__=='__main__':print(json.dumps(run(),indent=2))
