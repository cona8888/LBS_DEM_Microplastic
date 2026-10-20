"""Exact-configuration mobility cache. No interpolation or trajectory model."""
import hashlib,json
from pathlib import Path
import numpy as np

class GuardedMobility:
    def __init__(self,directory):
        directory=Path(directory)
        result=json.loads((directory/'results.json').read_text())
        contract_path=directory/'contract.json';op=directory/'operator.npz'
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        if not result.get('passed') or not all(result['checks'].values()):raise ValueError('unqualified operator')
        if digest(op)!=result['operator_hash'] or digest(contract_path)!=result['contract_hash']:raise ValueError('artifact hash mismatch')
        self.cfg=json.loads(contract_path.read_text())
        with np.load(op,allow_pickle=False) as data:
            self._M=data['mobility'].copy();R=data['resistance'].copy()
        if self._M.shape!=(6,6) or R.shape!=(6,6) or not np.isfinite(self._M).all() or not np.isfinite(R).all():raise ValueError('invalid operator')
        if np.linalg.norm(self._M@R-np.eye(6))>1e-10:raise ValueError('inconsistent inverse')
        self._M.setflags(write=False)
    def motion(self,force,torque,*,centre,axes,orientation,cavity_radius,mu):
        # Exact equality is deliberate: no validated geometric tolerance exists.
        for given,expected in [(centre,self.cfg['centre']),(axes,self.cfg['axes']),(orientation,np.eye(3))]:
            a=np.asarray(given,float);b=np.asarray(expected,float)
            if a.shape!=b.shape or not np.isfinite(a).all() or not np.array_equal(a,b):raise ValueError('geometry changed: recompute operator')
        if cavity_radius!=self.cfg['cavity_radius'] or mu!=self.cfg['mu']:raise ValueError('fluid or cavity changed')
        F=np.asarray(force,float);T=np.asarray(torque,float)
        if F.shape!=(3,) or T.shape!=(3,) or not np.isfinite(F).all() or not np.isfinite(T).all():raise ValueError('invalid load')
        L=self.cfg['length_scale'];z=self._M@np.r_[F,T/L]
        return z[:3],z[3:]/L
