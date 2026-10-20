"""Composition of independently exact native batch and trust implementations.

Neither source nor any physics/control is edited. This combination needs its
own exact replay and material whole-stack performance test before use.
"""
from contextlib import contextmanager
import native_batch_candidate_v1 as arrays
import native_trust_candidate_v4 as trust
prior=arrays.prior
ROOT,repair,compiled,batch=prior.ROOT,prior.repair,prior.compiled,prior.batch
constant,lsq=prior.constant,prior.lsq

@contextmanager
def scope(mode):
    if mode in ('baseline','direct'):
        with prior.scope('baseline' if mode=='baseline' else 'compiled_direct'):yield
    elif mode=='compiled_direct':
        with arrays.scope('compiled_direct'):
            saved=repair.prior.least_squares;repair.prior.least_squares=trust.least_squares
            try:yield
            finally:repair.prior.least_squares=saved
    else:raise ValueError('explicit benchmark mode required')

def warm():
    import numpy as np
    for n in (1,257):arrays.batch_body(np.ones(n),np.ones(6),np.ones(6),np.ones((9,6)),0,.3,.01,np.ones(6),np.eye(6),.03)
    batch.equation_arrays(np.zeros((1,9)),0,.3);batch.bracket_indices(np.zeros(1))
    prior.prior.column_norms(np.eye(9));prior.prior.max_abs(np.zeros(9));prior.prior.all_finite(np.zeros(9));prior.prior.all_finite(np.eye(9))
    for V in (np.eye(9),np.asfortranarray(np.eye(9))):
        for alpha in (None,0.,.03):trust.trust(9,9,np.ones(9),np.arange(1.,10.),V,.1,initial_alpha=alpha)
