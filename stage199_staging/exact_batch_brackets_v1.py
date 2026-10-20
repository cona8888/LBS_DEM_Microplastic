"""Original scan order and arithmetic; strict native bracket-index bookkeeping."""
from contextlib import contextmanager
import ast, inspect
import numpy as np
import exact_batch_arrays_v1 as previous
ROOT,compiled,original=previous.ROOT,previous.compiled,previous.original
equation_arrays=previous.equation_arrays

@compiled.numba.njit(cache=True,fastmath=False,parallel=False)
def bracket_indices(samples):
    indices=np.empty(max(0,len(samples)-1),np.int64);count=0
    for i in range(len(samples)-1):
        if not (np.isfinite(samples[i]) and np.isfinite(samples[i+1])):
            continue
        if samples[i]*samples[i+1]>=0:
            continue
        indices[count]=i;count+=1
    return indices[:count]

tree=ast.parse(inspect.getsource(original.scalar_solve));arrays=0;brackets=0
for node in ast.walk(tree):
    if isinstance(node,ast.FunctionDef) and node.name=='batch':
        positions=[i for i,v in enumerate(node.body) if isinstance(v,ast.Assign) and ast.unparse(v.targets[0]) in ('E','col','valid')]
        if len(positions)!=3 or positions!=list(range(positions[0],positions[0]+3)) or not isinstance(node.body[positions[-1]+1],ast.For):raise RuntimeError('original array structure changed')
        start=positions[0];node.body[start:start+4]=ast.parse('E, valid = _equation_arrays(w, stick, mu)').body;arrays+=1
    if isinstance(node,ast.For) and ast.unparse(node.iter)=='range(len(samples) - 1)':
        if not isinstance(node.body[0],ast.If) or ast.unparse(node.body[0].test)!='not np.isfinite(samples[i:i + 2]).all() or samples[i] * samples[i + 1] >= 0':raise RuntimeError('original bracket condition changed')
        if len(node.body[0].body)!=1 or not isinstance(node.body[0].body[0],ast.Continue):raise RuntimeError('original bracket condition body changed')
        node.iter=ast.parse('_bracket_indices(samples)',mode='eval').body;node.body=node.body[1:];brackets+=1
if (arrays,brackets)!=(1,1):raise RuntimeError('one exact array and bracket bookkeeping replacement required')
ast.fix_missing_locations(tree)
namespace={**original.__dict__,'_equation_arrays':equation_arrays,'_bracket_indices':bracket_indices}
exec(compile(tree,__file__+'::same_order_brackets','exec'),namespace)
scalar_solve=namespace['scalar_solve']

@contextmanager
def scope():
    saved=original.scalar_solve;original.scalar_solve=scalar_solve
    try:yield
    finally:original.scalar_solve=saved
