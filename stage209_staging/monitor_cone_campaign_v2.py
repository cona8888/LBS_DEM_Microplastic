"""Read-only v2: bind the auditor epoch through its actual affinity record.

The frozen v1 assumes auditor_launch.json has utc; original lifecycle omits it.
No production or frozen source changes. All original seal/receipt checks retained.
"""
from pathlib import Path
import json,sys,hashlib

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(expected):
    source=Path(__file__).with_name('monitor_cone_campaign_v1.py')
    design=Path('C:/MATDEM_MICROPLASTIC/stage209_designs/cone_feasibility_campaign_20260930/design_01.json')
    d=json.loads(design.read_text());assert sha(design)==expected and sha(source)==d['sources'][str(source)]
    text=source.read_text();before="item=ns['read'](file);epochs[item['pid']]=item['utc']"
    after="""item=ns['read'](file)
            if 'utc' not in item:
                assert file.name=='auditor_launch.json'
                affinity=ns['read'](root/'auditor.affinity.json')
                assert affinity['pid']==item['pid'] and affinity['design_sha256']==expected
                item=dict(item,utc=affinity['utc'])
            epochs[item['pid']]=item['utc']"""
    assert text.count(before)==1;text=text.replace(before,after)
    namespace=dict(__file__=str(source),__name__='_stage209_read_only_v2')
    exec(compile(text,str(source)+'::auditor_epoch_schema_v2','exec'),namespace)
    result=namespace['run'](expected)
    result.update(read_only_monitor_version=2,monitor_v1_preserved=True,monitor_v2_sha256=sha(__file__),auditor_creation_epoch_source='existing PID/design-bound auditor.affinity.json')
    return result

if __name__=='__main__':print(json.dumps(run(sys.argv[1]),indent=2))
