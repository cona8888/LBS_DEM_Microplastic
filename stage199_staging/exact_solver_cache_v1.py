"""Same TRF and scalar algorithm with bounded intra-call memo bookkeeping."""
from contextlib import contextmanager
import exact_solver_brackets_v1 as prior
import exact_batch_cache_v1 as batch
ROOT,repair,compiled=prior.ROOT,prior.repair,prior.compiled
constant,lsq=prior.constant,prior.lsq
least_squares,trf_no_bounds=prior.least_squares,prior.trf_no_bounds

@contextmanager
def scope(mode):
    if mode=='baseline':
        with prior.scope('baseline'):yield
    elif mode=='direct':
        with prior.scope('compiled_direct'):yield
    elif mode=='compiled_direct':
        saved=repair.prior.least_squares;repair.prior.least_squares=least_squares
        try:
            with compiled.scope(True),batch.scope():yield
        finally:repair.prior.least_squares=saved
    else:raise ValueError('explicit benchmark mode required')
