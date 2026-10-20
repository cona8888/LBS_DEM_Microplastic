"""Original numerical audit, with explicit inner-trial association only.

Two original association sites are replaced. Original numerical checks,
kinematics, clock, checkpoint, physical gates and terminal logic are unchanged.
"""
from pathlib import Path
import ast
import hashlib
import inspect
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'stage180_staging'))
import audit_optimized_record_v1 as original
import audit_contact_trial_trace_v2 as association


def build():
    source = inspect.getsource(original.evaluate)
    tree = ast.parse(source)
    coverage = links = returns = 0
    expected_guard = ast.parse("api.require(len(record['repairs'])==len(r['stage119_repair_calls'])==0,'no unrecorded fallback system')").body[0]
    expected_link = ast.parse("key=(attempt['dt_s'],*attempt['velocity']);api.require(velocity_keys[key]>0,'force-system output tied to an accepted trial');velocity_keys[key]-=1").body
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'evaluate':
            for i, stmt in enumerate(node.body):
                if ast.dump(stmt, include_attributes=False) == ast.dump(expected_guard, include_attributes=False):
                    node.body[i] = ast.parse('trial_audit = association.evaluate(record, before)').body[0]
                    coverage += 1
                if isinstance(stmt, ast.Return):
                    stmt.value.keys.extend([ast.Constant('trial_audit'), ast.Constant('fallback_force_systems'), ast.Constant('fallback_audits')])
                    stmt.value.values.extend([ast.Name(id='trial_audit', ctx=ast.Load()), ast.parse("trial_audit['fallback_records']", mode='eval').body, ast.parse("trial_audit['fallback_audits']", mode='eval').body])
                    returns += 1
        if isinstance(node, ast.If) and ast.dump(node.test, include_attributes=False) == ast.dump(ast.parse("attempt['accepted']", mode='eval').body, include_attributes=False):
            if [ast.dump(v, include_attributes=False) for v in node.body[:3]] != [ast.dump(v, include_attributes=False) for v in expected_link]:
                raise RuntimeError('original exact row association changed unexpectedly')
            node.body[:3] = ast.parse("api.require(trial_audit['passed'], 'complete exact inner-trial association')").body
            links += 1
    if (coverage, links, returns) != (1, 1, 1):
        raise RuntimeError('exactly two association sites and one summary required')
    ast.fix_missing_locations(tree)
    namespace = {**original.evaluate.__globals__, 'association': association}
    exec(compile(tree, str(Path(__file__).resolve())+'::association_only', 'exec'), namespace)
    return namespace['evaluate'], {'original_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'extended_ast_sha256': hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest(),
        'association_sites_replaced': 2, 'summary_extended': 1, 'other_ast_edits': 0}


evaluate, STRUCTURAL_IDENTITY = build()
