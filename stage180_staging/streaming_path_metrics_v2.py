"""Preserve stored nodes exactly at interpolation endpoints; v1 retained."""
import types
import numpy as np
import streaming_path_metrics_v1 as base


class Cursor(base.Cursor):
    def interpolate_pose(self,grid):
        out=super().interpolate_pose(grid)
        idx=np.searchsorted(self.times,grid,side='left')
        exact=self.times[idx]==grid
        out[exact]=self.nodes[idx[exact],1:7]
        if not np.isfinite(out).all():raise ValueError('nonfinite interpolated pose')
        return out


# The comparator equations, timing convention, normalization and limits are
# unchanged. Only the Cursor implementation differs in its execution namespace.
metrics=types.FunctionType(base.metrics.__code__,{**base.metrics.__globals__,'Cursor':Cursor},
                           name=base.metrics.__name__,argdefs=base.metrics.__defaults__)
