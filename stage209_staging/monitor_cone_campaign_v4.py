"""Read-only v4: distinguish a retired worker PID reused by another executable.

Retains original source/input/raw/receipt checks, v2 auditor association and v3
exact supervisor birth certificate. Never treats denied command access on an
active Python worker as retirement. No frozen source or production is changed.
"""
from pathlib import Path
import json, sys, psutil
import monitor_cone_campaign_v2 as previous

ROOT = Path('D:/MATDEM_MICROPLASTIC/stage209_runs/cone_feasibility_campaign_20260930/run_01')
DESIGN = Path('C:/MATDEM_MICROPLASTIC/stage209_designs/cone_feasibility_campaign_20260930/design_01.json')


def different_executable(process, role, argv):
    name = process.name()
    expected_name = Path(argv[0]).name if argv[0].lower().endswith('.exe') else Path(sys.executable).name
    if name.lower() == expected_name.lower():
        return None
    d = json.loads(DESIGN.read_text())
    assert role in {c['id'] for c in d['cases']}, 'nonworker identity cannot be bypassed'
    folder = ROOT / role
    seal = json.loads((folder / 'completion.json').read_text())
    result_path = folder / 'result.json'
    assert seal['design_sha256'] == previous.sha(DESIGN)
    assert seal['result_sha256'] == previous.sha(result_path)
    producer = json.loads(result_path.read_text())
    assert producer['design_sha256'] == seal['design_sha256']
    return dict(role=role, pid=process.pid, alive=False, original_worker_retired=True,
                pid_reused_by_different_executable=True, observed_current_process_name=name,
                original_expected_process_name=expected_name,
                retirement_result_sha256=seal['result_sha256'],
                retirement_seal_sha256=previous.sha(folder / 'completion.json'))


def guarded_template(source):
    d = json.loads(DESIGN.read_text())
    assert previous.sha(source) == d['sources'][str(source)], 'original seal-check template frozen'
    text = source.read_text()
    before = 'p=psutil.Process(pid);cmd=p.cmdline();expected=[str(v).lower() for v in argv]'
    after = '''p=psutil.Process(pid)
            replacement=different_executable(p,role,argv)
            if replacement is not None:
                processes.append(replacement);continue
            cmd=p.cmdline();expected=[str(v).lower() for v in argv]'''
    assert text.count(before) == 1
    return text.replace(before, after)


def run(expected):
    source = Path(__file__).with_name('monitor_cone_campaign_v1.py')
    d = json.loads(DESIGN.read_text())
    assert previous.sha(DESIGN) == expected and previous.sha(source) == d['sources'][str(source)]
    text = source.read_text()
    before = "text=SOURCE.read_text();mapping="
    assert text.count(before) == 1
    text = text.replace(before, 'text=guarded_template(SOURCE);mapping=')
    before = "item=ns['read'](file);epochs[item['pid']]=item['utc']"
    after = '''item=ns['read'](file)
            if 'utc' not in item:
                assert file.name=='auditor_launch.json'
                affinity=ns['read'](root/'auditor.affinity.json')
                assert affinity['pid']==item['pid'] and affinity['design_sha256']==expected
                item=dict(item,utc=affinity['utc'])
            epochs[item['pid']]=item['utc']'''
    assert text.count(before) == 1
    text = text.replace(before, after)
    before = "ns=dict(__name__='_stage209_read_only',__file__=__file__);"
    assert text.count(before) == 1
    text = text.replace(before, "ns=dict(__name__='_stage209_read_only',__file__=__file__,different_executable=different_executable);")
    namespace = dict(__file__=str(source), __name__='_stage209_read_only_v4', guarded_template=guarded_template)
    exec(compile(text, str(source) + '::unchanged_checks_generation_guard_v4', 'exec'), namespace)
    result = namespace['run'](expected)
    file = Path('C:/MATDEM_MICROPLASTIC/stage209_evaluations/cone_feasibility_campaign_20260930/launch_identity_01/results.json')
    certificate = json.loads(file.read_text()); seal = json.loads(file.with_name('completion.json').read_text())
    assert seal['passed'] and seal['results_sha256'] == previous.sha(file)
    assert certificate['passed'] and certificate['design_sha256'] == expected
    item = next(x for x in result['processes'] if x['role'] == 'supervisor'); bound = certificate['supervisor']
    if item.get('alive'):
        assert item['pid'] == bound['pid']
        process = psutil.Process(item['pid'])
        exact = process.cmdline() == bound['argv'] and abs(process.create_time() - bound['created']) < .001
        item.update(creation_epoch_bound=exact, bound_active_identity=exact and item['command_bound'],
                    creation_epoch_source='sealed original direct-child ancestry certificate')
    result.update(read_only_monitor_version=4, monitor_v4_sha256=previous.sha(__file__),
                  launch_identity_sha256=previous.sha(file),
                  retired_reused_pids=[p for p in result['processes'] if p.get('pid_reused_by_different_executable')])
    assert all(p.get('bound_active_identity') for p in result['processes'] if p.get('alive'))
    return result


if __name__ == '__main__': print(json.dumps(run(sys.argv[1]), indent=2))
