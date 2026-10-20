"""Per-stick memo of exactly repeated scalar beta calls; accounting unchanged.

No cache persists across stick modes, scalar solves or particle poses. Original
budget increment/check occurs before lookup. Vector-grid calls are not cached.
"""
from contextlib import contextmanager
import ast,copy
import exact_batch_brackets_v1 as prior
ROOT,compiled,original=prior.ROOT,prior.compiled,prior.original
equation_arrays,bracket_indices=prior.equation_arrays,prior.bracket_indices
tree=copy.deepcopy(prior.tree);outer=tree.body[0];insertions=0;changes=0
for node in ast.walk(outer):
    if isinstance(node,ast.For) and ast.unparse(node.target)=='stick':
        node.body.insert(0,ast.parse('_scalar_cache = {}').body[0]);insertions+=1
    if isinstance(node,ast.FunctionDef) and node.name=='batch':
        gate=next(i for i,v in enumerate(node.body) if isinstance(v,ast.If) and ast.unparse(v.test)=='calls > 2500')
        node.body[gate+1:gate+1]=ast.parse("_cache_key = beta.tobytes() if beta.dtype == np.float64 and beta.shape == (1,) else None\nif _cache_key is not None and _cache_key in _scalar_cache:\n    return _scalar_cache[_cache_key]").body
        if not isinstance(node.body[-1],ast.Return) or ast.unparse(node.body[-1].value)!='(determinant, E, H, rhs)':raise RuntimeError('original batch return changed')
        node.body[-1:]=ast.parse("_result = determinant, E, H, rhs\nif _cache_key is not None and len(_scalar_cache) < 256:\n    _scalar_cache[_cache_key] = _result\nreturn _result").body;changes+=1
if (insertions,changes)!=(1,1):raise RuntimeError('one bounded same-beta cache required')
ast.fix_missing_locations(tree)
namespace={**original.__dict__,'_equation_arrays':equation_arrays,'_bracket_indices':bracket_indices}
exec(compile(tree,__file__+'::same_beta_only','exec'),namespace)
scalar_solve=namespace['scalar_solve']

@contextmanager
def scope():
    saved=original.scalar_solve;original.scalar_solve=scalar_solve
    try:yield
    finally:original.scalar_solve=saved
