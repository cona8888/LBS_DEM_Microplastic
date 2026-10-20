"""Stateless, finite-factor timestep cap; original mechanics remain unchanged.

This is a prospectively tested numerical selector, not an error estimator or a
general event detector. It never sets dt proportional to gap/closing speed.
"""
from contextlib import contextmanager
from pathlib import Path
import ast
import copy
import hashlib
import numpy as np
import reconstruct_fixed_pose_v3 as reconstruction

modal=reconstruction.modal
POLICY=dict(schema='paper1.approaching-contact-timecap.v1',subdivision=16,
            lookahead_base_steps=4.,minimum_closing_over_U=.005)
SIGNATURE=('paper1.approaching-contact-timecap.v1',16,4.,.005)


def select(base_dt,near,q,a,speed,policy=POLICY,untruncated_dt=None):
    h=float(base_dt);a=float(a);speed=float(speed);v=np.asarray(q,float)
    full=h if untruncated_dt is None else float(untruncated_dt)
    if not (np.isfinite([h,a,speed]).all() and min(h,a,speed)>0 and v.shape==(6,) and np.isfinite(v).all()):
        raise ValueError('Finite positive timestep/scales and finite generalized velocity required')
    if not np.isfinite(full) or full<h:raise ValueError('Original untruncated cap must be finite and no smaller than base dt')
    if set(policy)!=set(POLICY) or tuple(policy[k] for k in ('schema','subdivision','lookahead_base_steps','minimum_closing_over_U'))!=SIGNATURE:
        raise ValueError('Only the frozen prospective selector policy is supported')
    triggers=[]
    for contact in near:
        gid,g,n,lever=contact[:4];g=float(g);n=np.asarray(n,float);lever=np.asarray(lever,float)
        if n.shape!=(3,) or lever.shape!=(3,) or not np.isfinite(np.r_[g,n,lever]).all():
            raise ValueError('Finite original contact operands required')
        closing=-float(n@v[:3]+np.cross(lever,n)@v[3:]/a)
        if closing>policy['minimum_closing_over_U']*speed and g<=policy['lookahead_base_steps']*closing*full:
            triggers.append(int(gid))
    # Cap against the original physical/numerical limit, then clip to the
    # remaining horizon. Dividing remaining time repeatedly would cause Zeno.
    selected=min(h,full/policy['subdivision']) if triggers else h
    if not np.isfinite(selected) or selected<=0 or selected>h:
        raise ValueError('A finite positive cap no greater than the original timestep is required')
    return selected,triggers


def compile_candidate(journal,speed,enabled=True):
    if type(enabled) is not bool:raise ValueError('Explicit Boolean selector switch required')
    tree=ast.parse(modal.GENERATED_SOURCE)
    fn=tree.body[0]
    loop=next(n for n in fn.body if isinstance(n,ast.Try)).body[0]
    index=next(i for i,n in enumerate(loop.body) if isinstance(n,ast.Assign)
        and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='accepted')
    original_tree=copy.deepcopy(tree)
    base=next(n for n in loop.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
              and n.targets[0].id=='dt')
    if not isinstance(base.value,ast.Call) or ast.unparse(base.value.func)!='min':
        raise RuntimeError('Original minimum timestep structure changed')
    args=[copy.deepcopy(x) for x in base.value.args if ast.unparse(x)!='horizon - t']
    if len(args)!=len(base.value.args)-1:raise RuntimeError('Exactly one remaining-horizon cap required')
    args.append(ast.parse('relaxation_fraction * tau_rot if rigid_rotation else max_dt',mode='eval').body)
    untruncated=ast.Call(ast.Name('min',ast.Load()),args,[])
    insertion=ast.parse('dt = _paper1_onset_cap(dt, 0., near, q, a, t, steps)').body[0]
    insertion.value.args[1]=untruncated
    loop.body.insert(index,insertion)
    reverted=copy.deepcopy(tree);rloop=next(n for n in reverted.body[0].body if isinstance(n,ast.Try)).body[0]
    del rloop.body[index]
    if ast.dump(reverted,include_attributes=False)!=ast.dump(original_tree,include_attributes=False):
        raise RuntimeError('Only one timestep selection assignment may differ from original source')
    def cap(h,full,near,q,a,t,steps):
        selected,ids=select(h,near,q,a,speed,untruncated_dt=full) if enabled else (float(h),[])
        witness=[[int(c[0]),float(c[1]),np.asarray(c[2],float).tolist(),np.asarray(c[3],float).tolist()] for c in near]
        journal.append(dict(time_s=float(t),steps=int(steps),base_dt_s=float(h),untruncated_dt_s=float(full),selected_dt_s=selected,
            velocity_generalized=np.asarray(q,float).tolist(),near=witness,trigger_grain_ids=ids))
        return selected
    ast.fix_missing_locations(tree)
    ns={**modal.CANDIDATE.__globals__,'_paper1_onset_cap':cap}
    exec(compile(tree,str(Path(__file__).resolve())+'::dt_only_candidate','exec'),ns)
    candidate=ns[fn.name]
    candidate.__defaults__=modal.CANDIDATE.__defaults__
    candidate.__kwdefaults__=copy.copy(modal.CANDIDATE.__kwdefaults__)
    return candidate,dict(only_change='One extra dt=min-cap assignment after all original caps, before pending restoration',
        original_source_digest=hashlib.sha256(modal.GENERATED_SOURCE.encode()).hexdigest(),
        ast_after_removing_cap_identical=True,policy=POLICY)


@contextmanager
def scope(journal,speed,enabled=True):
    saved=modal.CANDIDATE
    candidate,proof=compile_candidate(journal,speed,enabled)
    modal.CANDIDATE=candidate
    try:yield proof
    finally:modal.CANDIDATE=saved


def controls():
    contact=[(7,1e-9,np.array([1.,0.,0.]),np.zeros(3))]
    q=np.array([-.001,0.,0.,0.,0.,0.]);q0=q.copy()
    assert select(1e-6,contact,q,.0002,5e-5)==(1e-6/16,[7])
    assert select(1e-6,[],q,.0002,5e-5)==(1e-6,[])
    assert select(1e-6,contact,-q,.0002,5e-5)==(1e-6,[])
    assert select(1e-6,[(7,1e-4,*contact[0][2:])],q,.0002,5e-5)==(1e-6,[])
    assert select(1e-6,contact,np.zeros(6),.0002,5e-5)==(1e-6,[])
    threshold=.005*5e-5
    boundary=np.array([-threshold,0.,0.,0.,0.,0.])
    assert select(1e-6,[(7,0.,*contact[0][2:])],boundary,.0002,5e-5)[1]==[]
    boundary[0]=-np.nextafter(threshold,np.inf)
    assert select(1e-6,[(7,0.,*contact[0][2:])],boundary,.0002,5e-5)[1]==[7]
    gap=4*.001*1e-6
    assert select(1e-6,[(7,gap,*contact[0][2:])],q,.0002,5e-5)[1]==[7]
    assert select(1e-6,[(7,np.nextafter(gap,np.inf),*contact[0][2:])],q,.0002,5e-5)[1]==[]
    assert np.array_equal(q,q0)
    # At zero gap the cap remains finite; no asymptotic gap/closing timestep.
    assert select(1e-6,[(7,0.,*contact[0][2:])],q,.0002,5e-5)[0]==1e-6/16
    assert select(1e-10,[(7,0.,*contact[0][2:])],q,.0002,5e-5,untruncated_dt=1e-6)[0]==1e-10
    # Lever/rotation sign: (lever cross normal) dot qrot/a = -0.001m/s.
    spin=np.array([0.,0.,0.,0.,0.,.0002])
    assert select(1e-6,[(8,1e-9,np.array([1.,0.,0.]),np.array([0.,.001,0.]))],spin,.0002,5e-5)[1]==[8]
    for args in ((0.,contact,q,.0002,5e-5),(1e-6,contact,np.ones(5),.0002,5e-5)):
        try:select(*args)
        except ValueError:pass
        else:raise AssertionError('Invalid selector operands accepted')
    saved=modal.CANDIDATE
    with scope([],5e-5) as proof:assert modal.CANDIDATE is not saved and proof['ast_after_removing_cap_identical']
    assert modal.CANDIDATE is saved
    try:
        with scope([],5e-5):raise RuntimeError('restore-control')
    except RuntimeError:pass
    assert modal.CANDIDATE is saved
    return dict(passed=True,native_solver_calls=0,new_saved_steps=0,only_dt_selection_changes=True,
        original_caps_never_increased=True,no_gap_law_or_operand_mutation=True,
        stateless_finite_zero_gap_step=True,original_candidate_restored_on_success_and_error=True)


if __name__=='__main__':print(controls())
