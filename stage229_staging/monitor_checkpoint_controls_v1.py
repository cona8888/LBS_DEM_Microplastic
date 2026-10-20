"""Pure tamper controls and preserved terminal digest failure diagnosis."""
import ast, copy, hashlib, json
import campaign_common_v1 as c
import monitor_recovery_v4 as m


def run():
    c.bound(); c.environment()
    out = c.OUT/'monitor_checkpoint_repair_01'
    if out.exists(): raise RuntimeError('Create-only evidence; preserve prior attempt')
    physical = 'a'*64
    state = dict(t=1.0,steps=1,history=[[1.0,2.0]])
    checkpoint = dict(schema=1,contract='b'*64,state=state,state_sha256=m.canonical_checkpoint_digest(state))
    expected = m.canonical_checkpoint_digest(checkpoint)
    prefix = dict(design_sha256=physical,history_length=1,
        history_sha256=hashlib.sha256(json.dumps(state['history'],separators=(',',':'),allow_nan=False).encode()).hexdigest())
    rows = []
    def check(name, mutate=None, prefix_mutate=None, wrong_expected=False, passed=False):
        cp=copy.deepcopy(checkpoint);pr=copy.deepcopy(prefix)
        if mutate: mutate(cp)
        if prefix_mutate: prefix_mutate(pr)
        try:
            result=m.validate_terminal_checkpoint(cp,'c'*64 if wrong_expected else expected,pr,physical)
        except (ValueError,KeyError,TypeError) as error:
            assert not passed,name
            rows.append(dict(name=name,passed=True,negative_rejected=True,error=type(error).__name__))
        else:
            assert passed and result==expected,name
            rows.append(dict(name=name,passed=True,negative_rejected=False))
    check('valid_full_checkpoint',passed=True)
    check('changed_state',lambda x:x['state'].__setitem__('t',1.1))
    check('changed_declared_state_hash',lambda x:x.__setitem__('state_sha256','d'*64))
    check('wrong_expected_full_digest',wrong_expected=True)
    check('wrong_history_length',prefix_mutate=lambda x:x.__setitem__('history_length',2))
    check('wrong_history_hash',prefix_mutate=lambda x:x.__setitem__('history_sha256','e'*64))
    check('wrong_prefix_design',prefix_mutate=lambda x:x.__setitem__('design_sha256','f'*64))
    check('wrong_schema',lambda x:x.__setitem__('schema',2))
    check('empty_contract',lambda x:x.__setitem__('contract',''))
    check('history_not_list',lambda x:x['state'].__setitem__('history',{}))
    check('nan_state',lambda x:x['state'].__setitem__('t',float('nan')))
    check('nan_history',lambda x:x['state']['history'][0].__setitem__(0,float('nan')))
    check('infinite_state',lambda x:x['state'].__setitem__('t',float('inf')))
    check('boolean_schema',lambda x:x.__setitem__('schema',True))
    check('missing_history',lambda x:x['state'].pop('history'))
    check('changed_contract',lambda x:x.__setitem__('contract','d'*64))
    assert len(rows)==16
    folder=c.RUN/'run_02/s2_i0_fibre_f0p125'
    cp=c.read(folder/'checkpoint.json');terminal=c.sealed(folder/'results.json')
    original=terminal['final_checkpoint_sha256'];compact=c.digest(cp)
    assert original=='322fa2bc4b312fdb6fbe8df201b0971a5d66716291c53de84827b3bc1a062c5f'
    assert compact=='af5b3911754e894942c972ea6b420fd1173f3ddc9b82332d71b6b179a079effb'
    assert compact!=original
    exact=m.terminal_checkpoint_digest(cp,folder,original,terminal['physical_design_sha256'])
    assert exact==original
    source=ast.parse(m.PHYSICAL_DIGEST_SOURCE.read_text())
    fn=next(x for x in source.body if isinstance(x,ast.FunctionDef) and x.name=='digest')
    assert ast.unparse(fn) == "def digest(value):\n    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True, default=frozen.h.json_value).encode()).hexdigest()"
    import monitor_recovery_v2 as original_monitor
    before_run=original_monitor.run;before_inspect=original_monitor.inspect_process
    m.corrected_run_function(original_monitor)
    assert original_monitor.run is before_run and original_monitor.inspect_process is before_inspect
    segment=folder/'segment_00086'
    files=[folder/'checkpoint.json',folder/'prefix.json',folder/'results.json',folder/'completion.json',
        segment/'results.json',segment/'completion.json',segment/'call.json.seal.json']
    sources=[m.ORIGINAL,m.PHYSICAL_DIGEST_SOURCE,c.ROOT/'stage229_staging/continue_baseline_v3.py',
        c.ROOT/'stage229_staging/monitor_recovery_v3.py',c.ROOT/'stage179_staging/lossless_history_prefix_v1.py',
        c.ROOT/'stage229_staging/monitor_recovery_v4.py',c.ROOT/'stage229_staging/monitor_checkpoint_controls_v1.py']
    result=dict(passed=True,utc=c.utc(),authorization_sha256=c.sha(c.AUTH),numerical_calls=0,
        process_actions=0,live_process_inspections=0,number_of_controls=16,controls=rows,
        original_sources_and_active_bindings_unchanged=True,
        terminal_json_is_full_logical_checkpoint=True,packed_checkpoint_expansion_required=False,
        failure_preserved=dict(original_monitor_line=302,reason='Saved full terminal checkpoint digest',
            wrong_compact_digest=compact,expected_original_digest=original),
        exact_full_checkpoint_digest=exact,exact_state_digest=m.canonical_checkpoint_digest(cp['state']),
        declared_state_digest=cp['state_sha256'],history_length=len(cp['state']['history']),
        history_prefix_sha256=c.read(folder/'prefix.json')['history_sha256'],
        source_convention='Original Stage115 uses default JSON separators; administrative common digest uses compact separators. Only the terminal physical checkpoint expression changes.',
        run_ast_replacements=1,original_module_functions_unchanged=True,
        sources={str(p):c.sha(p) for p in sources},artifacts={str(p):c.sha(p) for p in files})
    c.commit(out/'results.json',result);c.commit(out/'completion.json',dict(passed=True,utc=c.utc(),results_sha256=c.sha(out/'results.json')))
    print(json.dumps(dict(passed=True,controls=16,results_sha256=c.sha(out/'results.json'),
        monitor_source_sha256=c.sha(c.ROOT/'stage229_staging/monitor_recovery_v4.py'),
        full_checkpoint_digest=exact,numerical_calls=0,process_actions=0),sort_keys=True))
    return result


if __name__=='__main__': run()
