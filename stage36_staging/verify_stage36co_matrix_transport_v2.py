"""Recovered manufactured/unit verification with JSON-safe scalars."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import matrix_release_transport_v1 as m
R=Path(__file__).resolve().parents[1];F=R/'stage36_evaluations/stage36co_matrix_transport_verification_20260911/test_01/failure.json';O=R/'stage36_evaluations/stage36co_matrix_transport_verification_20260911/test_02';O.mkdir(parents=True,exist_ok=False)
contract={'gates':{'constant_interpolation_abs':1e-14,'linear_interior_interpolation_abs':1e-12,'gradient_abs':1e-12,'orientation_norm_abs':1e-12,'periodic_margin_symmetry_abs':1e-12},'role':'code verification recovery; equations unchanged'};(O/'contract.json').write_text(json.dumps(contract,indent=2));assert json.loads(F.read_text())['accepted'] is False
f=np.empty((3,8,9,10));f[0]=2;f[1]=-3;f[2]=.5;e_const=float(np.max(np.abs(m.trilinear(f,[7.7,-.2,9.8])-[2,-3,.5])))
x,y,z=np.meshgrid(np.arange(8),np.arange(9),np.arange(10),indexing='ij');lin=2*x-3*y+.5*z+7;q=np.array([2.2,3.4,4.6]);e_lin=float(abs(m.trilinear(lin,q)-(2*q[0]-3*q[1]+.5*q[2]+7)))
u=np.zeros((3,16,16,16));u[0]=np.sin(2*np.pi*np.arange(16)[:,None,None]/16);g=m.periodic_gradient(u);expected=np.cos(2*np.pi*np.arange(16)/16)*np.sin(2*np.pi/16);e_grad=float(np.max(np.abs(g[0,0,:,0,0]-expected)))
p=np.array([1.,2.,3.]);p/=np.linalg.norm(p);p2=m.advance_orientation(p,np.array([[0,1,0],[-1,0,0],[0,0,0]],float),4,1e-2);e_norm=float(abs(np.linalg.norm(p2)-1));e_support=float(max(abs(m.ellipsoid_support([1,0,0],[1,0,0],4,1)-4),abs(m.ellipsoid_support([0,1,0],[1,0,0],4,1)-1)))
gr=m.PeriodicGrains([[.2,5,5]],[1.],10);e_sym=float(abs(gr.margin([9.7,5,5],[1,0,0],.4,.2)-gr.margin([.7,5,5],[1,0,0],.4,.2)))
checks={k:bool(v) for k,v in {'constant_interpolation':e_const<=1e-14,'linear_interior_interpolation':e_lin<=1e-12,'periodic_gradient_manufactured':e_grad<=1e-12,'orientation_normalized':e_norm<=1e-12,'support_limits':e_support<=1e-12,'periodic_margin_symmetry':e_sym<=1e-12}.items()};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();result={'passed':all(checks.values()),'checks':checks,'errors':{'constant':e_const,'linear':e_lin,'gradient':e_grad,'orientation_norm':e_norm,'support':e_support,'margin_symmetry':e_sym},'environment':{'python':sys.version,'numpy':np.__version__},'input_hashes':{str(p):sha(p) for p in [Path(__file__),Path(m.__file__),F,O/'contract.json']}};(O/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
