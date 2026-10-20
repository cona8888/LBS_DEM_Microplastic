"""Read-only generation guard, with explicit namespaces and template lineage.

Preserves failed v4/v5 development versions. Keeps original active-process,
source/input/raw/receipt gates, v2 auditor epoch and v3 supervisor birth binding.
Only a differently named executable plus sealed old worker completion can be
classified as PID reuse; unreadable active Python commands still fail closed.
"""
from pathlib import Path
import json, sys, psutil
import monitor_cone_campaign_v2 as original

ROOT = Path('D:/MATDEM_MICROPLASTIC/stage209_runs/cone_feasibility_campaign_20260930/run_01')
DESIGN = Path('C:/MATDEM_MICROPLASTIC/stage209_designs/cone_feasibility_campaign_20260930/design_01.json')
TEMPLATE_SHA = 'bfa4b45d6d15e6e65c0fa7e108a7f42384b685b209b0237624ae93a1c008ac2a'


def different_executable(process, role, argv):
    name = process.name()
    expected_name = Path(argv[0]).name if argv[0].lower().endswith('.exe') else Path(sys.executable).name
    if name.lower() == expected_name.lower(): return None
    d = json.loads(DESIGN.read_text())
    assert role in {c['id'] for c in d['cases']}, 'nonworker identity cannot be bypassed'
    folder = ROOT / role
    seal = json.loads((folder / 'completion.json').read_text())
    assert seal['design_sha256'] == original.sha(DESIGN)
    assert seal['result_sha256'] == original.sha(folder / 'result.json')
    assert json.loads((folder / 'result.json').read_text())['design_sha256'] == seal['design_sha256']
    return dict(role=role, pid=process.pid, alive=False, original_worker_retired=True,
                pid_reused_by_different_executable=True, observed_current_process_name=name,
                original_expected_process_name=expected_name, retirement_result_sha256=seal['result_sha256'],
                retirement_seal_sha256=original.sha(folder / 'completion.json'))


def guarded_template(source):
    assert source.resolve() == Path(__file__).resolve().parents[1] / 'stage200_staging/monitor_revised_campaign_v1.py'
    assert original.sha(source) == TEMPLATE_SHA, 'explicit original read-only template SHA'
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
    assert original.sha(DESIGN) == expected and original.sha(source) == d['sources'][str(source)]
    text = source.read_text()
    before = 'text=SOURCE.read_text();mapping='
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
    namespace = dict(__file__=str(source), __name__='_stage209_read_only_v6',
                     guarded_template=guarded_template, different_executable=different_executable)
    exec(compile(text, str(source) + '::unchanged_checks_generation_guard_v6', 'exec'), namespace)
    result = namespace['run'](expected)
    file = Path('C:/MATDEM_MICROPLASTIC/stage209_evaluations/cone_feasibility_campaign_20260930/launch_identity_01/results.json')
    certificate = json.loads(file.read_text()); seal = json.loads(file.with_name('completion.json').read_text())
    assert seal['passed'] and seal['results_sha256'] == original.sha(file)
    assert certificate['passed'] and certificate['design_sha256'] == expected
    item = next(x for x in result['processes'] if x['role'] == 'supervisor'); bound = certificate['supervisor']
    if item.get('alive'):
        assert item['pid'] == bound['pid']
        process = psutil.Process(item['pid'])
        exact = process.cmdline() == bound['argv'] and abs(process.create_time() - bound['created']) < .001
        item.update(creation_epoch_bound=exact, bound_active_identity=exact and item['command_bound'],
                    creation_epoch_source='sealed original direct-child ancestry certificate')
    result.update(read_only_monitor_version=6, monitor_v6_sha256=original.sha(__file__),
                  launch_identity_sha256=original.sha(file), read_only_template_sha256=TEMPLATE_SHA,
                  retired_reused_pids=[p for p in result['processes'] if p.get('pid_reused_by_different_executable')])
    assert all(p.get('bound_active_identity') for p in result['processes'] if p.get('alive'))
    return result


if __name__ == '__main__': print(json.dumps(run(sys.argv[1]), indent=2))
