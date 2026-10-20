"""Zero-action wrapper restoration controls and immutable diagnosis association."""
import importlib, json
import campaign_common_v1 as c
import monitor_recovery_v3 as m

DIAGNOSIS = c.OUT/'monitor_identity_diagnosis_01/results.json'
DIAGNOSIS_SHA256 = '52a14768092e190878a9a349c9ebdac44de5fbb300afae7fc8b1a2e5930fccb7'
CONTROLS = c.OUT/'monitor_identity_repair_01/results.json'
CONTROLS_SHA256 = '0fddec8db54e0f8d9e4bd7455ea741ec508963602c8dfb682b960b82851ee62d'


def run():
    c.bound(); c.environment()
    target = c.OUT/'monitor_identity_repair_provenance_01'
    if target.exists():
        raise RuntimeError('Create-only association evidence; existing attempt preserved')
    if c.sha(DIAGNOSIS) != DIAGNOSIS_SHA256 or c.sha(CONTROLS) != CONTROLS_SHA256:
        raise RuntimeError('Exact frozen diagnosis and prior controls required')
    diagnosis = c.sealed(DIAGNOSIS)
    controls = c.sealed(CONTROLS)
    assert controls['passed'] is True and controls['number_of_controls'] == 14
    assert controls['numerical_calls'] == controls['process_actions'] == controls['live_process_inspections'] == 0
    c.verify(controls['sources']); c.verify(controls['inputs'])
    original = importlib.import_module('monitor_recovery_v2')
    original_run = original.run
    original_inspect = original.inspect_process
    rows = []
    class ExpectedFakeFailure(Exception):
        pass
    try:
        def fake_success():
            assert original.inspect_process is m.inspect_process
            return {'fake_run_only': True}
        original.run = fake_success
        assert m.run() == {'fake_run_only': True}
        assert original.inspect_process is original_inspect
        rows.append(dict(name='adapter_restores_original_inspection_after_fake_success', passed=True))
        def fake_failure():
            assert original.inspect_process is m.inspect_process
            raise ExpectedFakeFailure('No real monitor or process was inspected')
        original.run = fake_failure
        try:
            m.run()
        except ExpectedFakeFailure:
            pass
        else:
            raise AssertionError('Fake monitor failure must propagate')
        assert original.inspect_process is original_inspect
        rows.append(dict(name='adapter_restores_original_inspection_after_fake_error', passed=True))
    finally:
        original.run = original_run
        original.inspect_process = original_inspect
    result = dict(passed=True, utc=c.utc(), authorization_sha256=c.sha(c.AUTH),
        numerical_calls=0, transport_steps=0, live_process_inspections=0, process_actions=0,
        original_monitor_and_all_active_bindings_unchanged=True,
        original_diagnosis_preserved=True, prior_fake_identity_controls=14,
        additional_fake_wrapper_controls=rows,
        association='The separately versioned read-only adapter corrects only unconditional command inspection after a demonstrably different process birth. Its frozen diagnosis is historical evidence; no ongoing identity is assumed from that snapshot.',
        sources={str(m.ORIGINAL):c.sha(m.ORIGINAL), str(m.__file__):c.sha(m.__file__), str(__file__):c.sha(__file__)},
        inputs={str(DIAGNOSIS):c.sha(DIAGNOSIS), str(DIAGNOSIS.parent/'completion.json'):c.sha(DIAGNOSIS.parent/'completion.json'),
            str(CONTROLS):c.sha(CONTROLS), str(CONTROLS.parent/'completion.json'):c.sha(CONTROLS.parent/'completion.json')})
    c.commit(target/'results.json', result)
    c.commit(target/'completion.json', dict(passed=True, utc=c.utc(), results_sha256=c.sha(target/'results.json')))
    print(json.dumps(dict(passed=True, prior_controls=14, additional_wrapper_controls=2,
        results_sha256=c.sha(target/'results.json'), numerical_calls=0, process_actions=0), sort_keys=True))
    return result


if __name__ == '__main__':
    run()
