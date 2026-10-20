# Stage36L — bounded full CPU immersed-sphere reference

Question: does the Stage36K interface work in a complete discrete flow step,
including an active nonuniform test? This is solver integration verification,
not drag validation, fibre release, or a replacement of accepted production code.

New project split reference: FP64 periodic D3Q19 BGK tau=.8, all lattice nodes
always active. Arrays [q,x,y,z]; lattice dx=dt=rho0=1. Each step:
1. Collide and periodic pull stream without force.
2. Move prescribed sphere centre to end-of-step position.
3. Build Stage36K four-point J and S=J^T (h=1, integrated marker impulses).
4. Solve A lambda = Ub-J u*, A=J diag(1/rho*) J^T. No regularization or pinv.
5. Grid impulse g=J^T lambda; endpoint velocity u+=u*+g/rho*.
6. f+=feq(rho*,u+) - feq(rho*,u*) at fixed density.
This endpoint split explicitly defines raw endpoint momentum; it is not a Guo
half-force implementation. Equilibrium-difference forcing has literature precedent,
but this combination's temporal/continuum accuracy is unqualified. Do not claim
second-order flow accuracy from Stage36K interpolation convergence.
Reference context: Kupershtokh et al. (2009), DOI10.1016/j.camwa.2009.02.024,
equilibrium-difference forcing; Uhlmann (2005), DOI10.1016/j.jcp.2005.03.017,
interior momentum contribution. No claim to reproduce either published solver.

Surface points: deterministic Fibonacci sphere; counts N12=32,N16=56,N24=128.
Independent probes: 2*count directions with an angular phase offset .37 radians.
These probes are NOT enforced. Report their slip separately from marker slip.
Condition number cap1e10; finite positive populations; no clipping/rescaling.

Mass outside sphere is estimated as total lattice mass minus a geometric sphere
volume quadrature of density using local trilinear interpolation, NOT the smoothed
force kernel. Same quadrature integrates momentum density p, not rho0*u.
Primary4x8x16=512 body-fixed points, Jacobian weights; final8x16x32 cross-check.
This is an approximate geometric integral, not an exact cut-cell face-flux budget.
Force candidate per step: -sum(lambda)+P_inside(t+1)-P_inside(t), no other body
forces. Do not claim physical force validation merely from its accounting closure.
Torque, moving bodies crossing box seams and body dynamics are deferred.

Frozen12 flow conditions, maximum N24,576steps,180 seconds CPU flow cap:
- uniform co-motion N12,16,24 forward/reverse Ux=+/-.08/N, each N^2 steps;
- stationary rest N16;
- uniform N16 forward centre-x phase+.5;
- nonuniform N12,16,24 forward, initial u=U+[.02/N*sin(2*pi*y/N),0,0];
- N16 nonuniform forward with interface disabled (negative control).
All centres initially [N/2+.13+phase,N/2+.17,N/2+.19], R=N/5.
Physical scaling dx=1/N,dt=1/N^2; marker counts co-refine, not an independent
marker-spacing study. Nonuniform flow is an integration challenge with no analytic
transient drag comparator; its force is not expected to vanish.

Predeclared gates for enabled cases: total mass relative drift<=1e-10;
exterior mass relative drift<=1e-6; full momentum ledger relative<=1e-12;
enforced-marker absolute slip<=1e-10; rho error<=.01; positive finite populations.
Uniform-only gates rho/u errors<=1e-10 and force candidate<=1e-9 LU.
Nonuniform probe-slip/initial perturbation amplitude<=.05; final fine/coarse
exterior mass discrepancy normalized by exterior initial mass<=1e-6.
Disabled control must fail marker-slip gate; it is not counted as a physical pass.
Save every-step metrics and initial/final arrays plus first full step per case.
All133 prior unit tests plus new solver tests must pass before flow cases.
Any failed physical gate remains failed. No parameter tuning or production run.
Next steps depend on these results; time, marker and nonzero-drag qualification
remain required even if every integration gate passes.
