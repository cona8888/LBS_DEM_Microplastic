"""Bounded-block original-convention path comparison, no whole time vectors.

Positions/axes use the frozen piecewise-linear nodal convention. Generalized
velocity is constant on its accepted interval. Stop at the earlier audited end;
never extrapolate an exported path or realign impact times.
"""
import math
import numpy as np


class Cursor:
    def __init__(self,blocks,initial,end):
        self.blocks=iter(blocks);self.previous=np.asarray(initial,float)
        if self.previous.shape!=(13,) or not np.isfinite(self.previous).all():raise ValueError('finite 13-value initial node')
        if not np.isfinite(end) or end<=self.previous[0]:raise ValueError('positive audited time coverage')
        self.expected_end=float(end);self.nodes=None;self.count=0;self.maximum_block_rows=0;self.done=False;self.load()

    def load(self):
        if self.nodes is not None:self.previous=self.nodes[-1].copy()
        try:rows=np.asarray(next(self.blocks),float)
        except StopIteration:
            if self.previous[0]!=self.expected_end:raise ValueError('incomplete audited path blocks')
            self.done=True;return
        if rows.ndim!=2 or rows.shape[1]!=13 or len(rows)==0 or not np.isfinite(rows).all():raise ValueError('nonempty finite 13-column block required')
        if rows[0,0]<=self.previous[0] or not np.all(np.diff(rows[:,0])>0) or rows[-1,0]>self.expected_end:raise ValueError('invalid monotone block clock')
        self.nodes=np.vstack([self.previous,rows]);self.times=self.nodes[:,0];self.count+=len(rows)
        self.maximum_block_rows=max(self.maximum_block_rows,len(rows))

    def interpolate_pose(self,grid):
        if grid[0]<self.times[0] or grid[-1]>self.times[-1]:raise ValueError('no pose extrapolation')
        idx=np.clip(np.searchsorted(self.times,grid,side='left'),1,len(self.times)-1)
        frac=(grid-self.times[idx-1])/(self.times[idx]-self.times[idx-1])
        return self.nodes[idx-1,1:7]+frac[:,None]*(self.nodes[idx,1:7]-self.nodes[idx-1,1:7])

    def interval_velocities(self,right_endpoints):
        idx=np.searchsorted(self.times,right_endpoints,side='left')
        if np.any(idx==0) or np.any(idx>=len(self.times)):raise ValueError('accepted velocity interval missing')
        return self.nodes[idx,7:13]


def metrics(blocks_a,blocks_b,initial_a,initial_b,end_a,end_b,minor_radius,speed):
    if not np.isfinite([minor_radius,speed]).all() or min(minor_radius,speed)<=0:raise ValueError('positive finite normalization scales')
    a,b=Cursor(blocks_a,initial_a,end_a),Cursor(blocks_b,initial_b,end_b)
    start=float(a.previous[0])
    if b.previous[0]!=start:raise ValueError('same physical starting clock required')
    stop=min(float(end_a),float(end_b));left=start;pieces=[];pose=axis=sup=0.;intervals=0;maximum_grid=0
    while not (a.done or b.done):
        right=min(a.times[-1],b.times[-1])
        if right<=left or right>stop:raise ValueError('invalid common block interval')
        interior=[x.times[(x.times>left)&(x.times<right)] for x in [a,b]]
        grid=np.unique(np.r_[left,interior[0],interior[1],right]);maximum_grid=max(maximum_grid,len(grid))
        delta=a.interpolate_pose(grid)-b.interpolate_pose(grid)
        pose=max(pose,float(np.linalg.norm(delta[:,:3],axis=1).max())/minor_radius)
        axis=max(axis,float(np.linalg.norm(delta[:,3:],axis=1).max()))
        qa,qb=a.interval_velocities(grid[1:]),b.interval_velocities(grid[1:]);errors=np.linalg.norm(qa-qb,axis=1)/speed
        pieces.append(float(np.dot(errors,np.diff(grid))));sup=max(sup,float(errors.max()));endpoint=float(errors[-1]);intervals+=len(grid)-1;left=right
        if right==a.times[-1]:a.load()
        if right==b.times[-1]:b.load()
    if left!=stop:raise ValueError('audited common endpoint not reached')
    integral=math.fsum(pieces)
    return {'common_start_s':start,'common_stop_s':stop,'common_duration_s':stop-start,'whole_position_over_b_max':pose,
            'whole_axis_vector_norm_max':axis,'endpoint_q_over_U_max':endpoint,'mean_L1_q_over_U_max':integral/(stop-start),
            'integrated_q_error_over_U_s':integral,'interval_velocity_sup_over_U_diagnostic_only':sup,
            'endpoint_convention':'At the earlier actual end time; no extension beyond outlet export.',
            'working_set':{'maximum_source_block_rows':max(a.maximum_block_rows,b.maximum_block_rows),'maximum_union_grid_rows':maximum_grid,
                           'summation_partials':len(pieces),'union_intervals':intervals},
            'nonlimiting_tail':'May remain unread by comparator; full-path integrity and endpoint must be established separately by the raw-record auditor.'}
