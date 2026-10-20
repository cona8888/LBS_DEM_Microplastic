"""Read-only v3: exact supervisor birth identity, retaining all frozen checks."""
from pathlib import Path
import json,sys,psutil
import monitor_cone_campaign_v2 as previous

def run(expected):
    result=previous.run(expected)
    file=Path('C:/MATDEM_MICROPLASTIC/stage209_evaluations/cone_feasibility_campaign_20260930/launch_identity_01/results.json')
    certificate=json.loads(file.read_text());seal=json.loads(file.with_name('completion.json').read_text())
    assert seal['passed'] and seal['results_sha256']==previous.sha(file) and certificate['passed'] and certificate['design_sha256']==expected
    item=next(x for x in result['processes'] if x['role']=='supervisor');bound=certificate['supervisor']
    if item.get('alive'):
        assert item['pid']==bound['pid']
        process=psutil.Process(item['pid']);exact=process.cmdline()==bound['argv'] and abs(process.create_time()-bound['created'])<.001
        item.update(creation_epoch_bound=exact,bound_active_identity=exact and item['command_bound'],creation_epoch_source='sealed original direct-child ancestry certificate')
    result.update(read_only_monitor_version=3,monitor_v3_sha256=previous.sha(__file__),launch_identity_sha256=previous.sha(file))
    return result

if __name__=='__main__':print(json.dumps(run(sys.argv[1]),indent=2))
