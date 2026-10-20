"""Extend frozen Stage180 audit only with independently recorded fallbacks.

An AST-constrained replacement substitutes the old 'no fallback' coverage
assertion with complete original-law fallback audits. All other checks and
equations remain byte-for-byte the same AST. Version 1 remains untouched.
"""
from pathlib import Path
import ast,copy,hashlib,inspect,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage180_staging'))
import audit_optimized_record_v1 as original
import audit_fallback_systems_v1 as fallback


def build():
    source=inspect.getsource(original.evaluate);tree=ast.parse(source);replacements=0;returns=0
    for node in ast.walk(tree):
        if isinstance(node,ast.FunctionDef) and node.name=='evaluate':
            for i,statement in enumerate(node.body):
                if (isinstance(statement,ast.Expr) and isinstance(statement.value,ast.Call)
                    and len(statement.value.args)==2 and isinstance(statement.value.args[1],ast.Constant)
                    and statement.value.args[1].value=='no unrecorded fallback system'):
                    expected=ast.parse("api.require(len(record['repairs'])==len(r['stage119_repair_calls'])==0,'no unrecorded fallback system')").body[0]
                    if ast.dump(statement,include_attributes=False)!=ast.dump(expected,include_attributes=False):raise RuntimeError('unexpected original fallback guard')
                    node.body[i]=ast.parse("fallback_audits = fallback.record_coverage(record, verified.job.fast.old.NAME)").body[0];replacements+=1
                if isinstance(statement,ast.Return):
                    if not isinstance(statement.value,ast.Dict):raise RuntimeError('unexpected original audit return')
                    statement.value.keys.extend([ast.Constant('fallback_force_systems'),ast.Constant('fallback_audits')])
                    statement.value.values.extend([ast.parse('len(fallback_audits)',mode='eval').body,ast.Name(id='fallback_audits',ctx=ast.Load())]);returns+=1
    if replacements!=1 or returns!=1:raise RuntimeError('exactly one coverage guard and summary extension required')
    ast.fix_missing_locations(tree);namespace={**original.evaluate.__globals__,'fallback':fallback}
    exec(compile(tree,str(Path(__file__).resolve())+'::verified_ast_extension','exec'),namespace)
    identity={'original_function_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'extended_ast_sha256':hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),
        'coverage_assertions_replaced':replacements,'return_summaries_extended':returns,'other_ast_edits':0}
    return namespace['evaluate'],identity


evaluate,STRUCTURAL_IDENTITY=build()
