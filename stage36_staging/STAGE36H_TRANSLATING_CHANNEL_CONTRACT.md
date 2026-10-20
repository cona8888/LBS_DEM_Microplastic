# Stage36H: complete CPU prescribed translating-channel benchmark

Scope: FP64 BGK D3Q19, fields homogeneous in x,z and varying in y; unit cross
section. Fluid lies between parallel walls y=L(t) and L(t)+N. Both walls move
normally at V; tangential velocities are 0 and U for Couette, or both zero for
uniform translation. Sand, fibres, outlets, rigid-body dynamics, GPU execution,
and production-solver edits are excluded. All units below are lattice units.

tau=.8, cs^2=1/3, nu=.1. The full populations are used, not the production
shifted FP32 representation. Constant rho reference =1 in the boundary formula.
Initial condition is equilibrium at rho=1, uy=V, ux=U*(y-L)/N (or ux=0).
The continuum comparator is that same uniform-density/linear-velocity field
advected with the channel. An initial kinetic transient is permitted; final
profiles and late-time tractions are compared, but health/balances cover ALL steps.

Boundary: linear Bouzidi interpolation as given in Peng et al. (2016), equations
13 and 15. Incoming lattice direction k points from wall into fluid, distance
q is the normal wall-to-fluid-centre distance in lattice spacings. With outgoing
o=opp(k), wall velocity uw and B=6*w[k]*(c[k] dot uw):

    q<=.5: f_in = 2*q*f_post[o,j] + (1-2*q)*f_post[o,j+inward] + B
    q> .5: f_in = (f_post[o,j]+B)/(2*q) + (2*q-1)*f_old[k,j]/(2*q)

Explicit operator ordering per step: (1) collide on fluid nodes of mask at t;
(2) stream/interpolate on the SAME mask, boundary position at t; (3) advance
prescribed walls to t+1; (4) refill a newly exposed node with 2*f1-f2 from two
retained fluid nodes inward along y, then zero covered cells. No clipping,
reservoir, local pooling, density rescale, or moment adjustment is used. Reject
nonpositive/nonfinite populations and unavailable stencils. This is a documented
project combination, not a claim to reproduce a complete published implementation.

Each step logs independently computed collision mass/momentum defect, incoming
minus outgoing boundary mass, lab-frame boundary impulse, signed status-change
mass/momentum at each wall, and total pre/post mass/momentum. Close BOTH the
operator ledger and total mass drift; an exact ledger is not zero physical drift.
Status impulses are bookkeeping diagnostics, not forces applied to any body.
The summed boundary+status impulse per wall is a traction candidate tested below,
not an assumed generally correct Galilean-invariant force method.

Frozen cases (12): N=8,16,32 each with uniform V=.08/N,U=0; translated shear
V=.08/N,U=.08/N; static shear V=0,U=.08/N. Also N16 reversed V=-.08/16,
reversed shear U=-.08/16, and uniform V=U=0. Initial L=N+sqrt(2)/10. Grid has
4*N nodes centred at j+.5. End at 10*N^2 steps (theta=nu*t/N^2=1).
dx=1/N, dt=1/N^2 => fixed physical H=1, nu=.1, moving speeds .08, Re=.8.
This is diffusive refinement, not independent space/time convergence. Each moving
case crosses at least six cells. Width and fluid-node count must stay exactly N.

Late traction average spans the last FIVE full cell-crossing periods, each
1/abs(V) steps (integer for these cases), avoiding fractional-cycle sampling.
For static cases use last 500 steps. Expected wall x forces: [+nu*U/N,-nu*U/N].
Expected wall y forces: [-1/3,+1/3]. Report the separate boundary and status parts,
as well as the candidate sum and temporal spikes. The initial equilibrium is not
the exact discrete non-equilibrium steady state; no observed order is inferred
from final profiles unless data support it.

Acceptance frozen before execution: positive finite fluid and zero solid;
constant node count N; per-step mass and momentum ledger residual <=1e-11;
whole-run relative mass drift <=1e-6; max density deviation <=.01;
final ux max error/max(abs(U),.001)<=.02 and uy max error<=1e-5;
late wall shear error <=5% for shear cases, <=1e-10 absolute for zero shear;
late normal wall traction error <=.01 absolute. Uniform cases additionally
require velocity error <=1e-10 and density deviation <=1e-10.
All 95 prior unit tests run unchanged plus new operator tests. Maximum 12 CPU
cases, N<=32, 10240 steps/case, total execution cap 120 seconds.

Record failed gates without retuning. Even if planar tests pass, curved moving
geometry, physical force extraction, outlet accounting, wet contacts and coupled
fibre dynamics remain unqualified. No release prediction is authorized here.

Primary reference inspected 2026-09-06: Peng et al., Computers & Mathematics with
Applications 72 (2016) 349-374, DOI 10.1016/j.camwa.2015.08.027, sections 3.1.1
and 5.1.1. Used for interpolation/refill formulas, not experimental validation.
https://research.me.udel.edu/lwang/reprints/Peng_etal_CAMWA_2016.pdf
