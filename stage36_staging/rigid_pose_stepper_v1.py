"""Pose-dependent inertialess RK2; world-frame angular velocity, no contacts."""
import numpy as np
def exp_rotation(w):
    a=np.linalg.norm(w)
    K=np.array([[0,-w[2],w[1]],[w[2],0,-w[0]],[-w[1],w[0],0.]])
    if a<1e-8:return np.eye(3)+(1-a*a/6)*K+(.5-a*a/24)*(K@K)
    return np.eye(3)+np.sin(a)/a*K+(1-np.cos(a))/a**2*(K@K)
def integrate(x0,Q0,load,provider,clearance,duration,steps):
    x=np.array(x0,float);Q=np.array(Q0,float);f=np.array(load,float)
    if x.shape!=(3,) or Q.shape!=(3,3) or f.shape!=(6,) or not all(np.isfinite(v).all() for v in [x,Q,f]):raise ValueError('invalid inputs')
    if np.linalg.norm(Q.T@Q-np.eye(3))>1e-10 or abs(np.linalg.det(Q)-1)>1e-10:raise ValueError('invalid orientation')
    if type(steps) is not int or steps<1 or not np.isfinite(duration) or duration<=0:raise ValueError('invalid time')
    dt=duration/steps;xs=[x.copy()];qs=[Q.copy()]
    def check(p,R):
        gap=float(clearance(p.copy(),R.copy()))
        if not np.isfinite(gap) or gap<=0:raise ValueError('clearance violated')
    def velocity(p,R):
        check(p,R);M=np.asarray(provider(p.copy(),R.copy()),float)
        if M.shape!=(6,6) or not np.isfinite(M).all() or not np.allclose(M,M.T,rtol=1e-10,atol=1e-14) or np.linalg.eigvalsh(M).min()<=0:raise ValueError('invalid mobility')
        return M@f
    for _ in range(steps):
        z=velocity(x,Q);mid_x=x+dt/2*z[:3];mid_Q=exp_rotation(dt/2*z[3:])@Q
        z=velocity(mid_x,mid_Q);new_x=x+dt*z[:3];new_Q=exp_rotation(dt*z[3:])@Q
        check(new_x,new_Q);x,Q=new_x,new_Q;xs.append(x.copy());qs.append(Q.copy())
    return np.array(xs),np.array(qs)
