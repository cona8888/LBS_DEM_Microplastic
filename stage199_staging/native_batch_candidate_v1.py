"""Unqualified strict batch preparation, retaining original determinant kernel.

No scalar scan, root, rank, solve, budget, or physical decision changes.
Must pass exact intermediate-array and held-outer checks before trajectory use.
"""
from contextlib import contextmanager
import ast,inspect
import numpy as np
from numpy.linalg import _umath_linalg
import exact_dense_dispatch_v1 as prior
ROOT,repair,compiled,batch=prior.ROOT,prior.repair,prior.compiled,prior.batch
constant,lsq=prior.constant,prior.lsq
equation_arrays=batch.equation_arrays

@compiled.numba.njit(cache=True,fastmath=False,parallel=False,error_model='numpy')
def batch_body(beta,q0,direction,J,stick,mu,vs,v,B,fs):
    n=len(beta);q=np.empty((n,6))
    for i in range(n):
        for j in range(6):q[i,j]=q0[j]+beta[i]*direction[j]
    w=q@J.T
    E,valid=equation_arrays(w,stick,mu)
    H=np.empty((n,6,5))
    for i in range(n):H[i]=J.T@E[i]
    rhs=((vs*q-v)@B.T)/fs
    matrix=np.empty((n,6,6))
    for i in range(n):
        for j in range(6):
            for k in range(5):matrix[i,j,k]=H[i,j,k]
            matrix[i,j,5]=rhs[i,j]
    with compiled.numba.objmode(determinant='float64[::1]'):
        determinant=_umath_linalg.det(matrix,signature='d->d')
    for i in range(n):
        if not valid[i]:determinant[i]=np.nan
    return determinant,E,H,rhs

tree=ast.parse(inspect.getsource(batch.original.scalar_solve));replaced=0;brackets=0
# Reuse original bracket bookkeeping and original scalar algorithm. Only its
# nested batch's arithmetic preparation is substituted, after the same call cap.
class Batch(ast.NodeTransformer):
    def visit_For(self,node):
        global brackets
        if ast.unparse(node.iter)=='range(len(samples) - 1)':
            if ast.unparse(node.body[0].test)!='not np.isfinite(samples[i:i + 2]).all() or samples[i] * samples[i + 1] >= 0':raise RuntimeError('original bracket guard')
            node.iter=ast.parse('_bracket_indices(samples)',mode='eval').body;node.body=node.body[1:];brackets+=1
        return self.generic_visit(node)
    def visit_FunctionDef(self,node):
        global replaced
        if node.name=='batch':
            start=next(i for i,x in enumerate(node.body) if isinstance(x,ast.Assign) and ast.unparse(x.targets[0])=='q')
            node.body[start:]=ast.parse('return _batch_body(beta,q0,direction,J,stick,mu,vs,v,B,fs)').body;replaced+=1
        return self.generic_visit(node)
Batch().visit(tree)
if (replaced,brackets)!=(1,1):raise RuntimeError('one nested batch substitution, qualified bracket bookkeeping retained')
ast.fix_missing_locations(tree)
ns={**prior.scalar_solve.__globals__,'_batch_body':batch_body}
exec(compile(tree,__file__+'::same_scan_native_batch','exec'),ns);scalar_solve=ns['scalar_solve']

@contextmanager
def scope(mode):
    if mode in ('baseline','direct'):
        with prior.scope('baseline' if mode=='baseline' else 'compiled_direct'):yield
    elif mode=='compiled_direct':
        with prior.scope('compiled_direct'):
            saved=batch.original.scalar_solve;batch.original.scalar_solve=scalar_solve
            try:yield
            finally:batch.original.scalar_solve=saved
    else:raise ValueError('explicit benchmark mode required')
