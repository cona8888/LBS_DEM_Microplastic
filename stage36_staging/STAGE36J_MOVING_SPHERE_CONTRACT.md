# Stage36J — prescribed co-moving sphere, complete 3D CPU check

Use the selected Stage36I POST boundary time level. New CPU FP64 D3Q19 BGK
implementation, tau=.8, nu=.1, reference rho=1, triply periodic box. Arrays are
explicitly [q,x,y,z] here, unlike the older CUDA [q,z,y,x] convention. No engine
or production code is changed. Sphere motion is prescribed, never integrated.
No sand/fibres, gravity, outlet, release, wet contact or relative-flow drag.

For fluid destination x and incoming direction c, source x-c is solid. Solve
|x-q*c-centre|^2=R^2 for the FIRST ray intersection q in (0,1]. Apply corrected
linear interpolated bounce-back: q<=.5 uses outgoing POST populations at x and
x+c; q>.5 uses outgoing POST and incoming POST at x. Moving correction is
6*w*(c dot U). All boundary links use the prescribed translational wall speed.

Order: collision on old fluid; periodic pull stream and interpolation on old
mask/geometry; update centre; refill exposed cells by averaged linear two-point
extrapolation over available D3Q19 rays with BOTH donors retained fluid; zero
covered cells. Reject missing donors, invalid q and nonpositive/nonfinite
populations. No clipping, rescaling, mass reservoir or fictitious density repair.
The source-neighbour interpolation and refill are independently unit tested.

Frozen 8 cases: N=12,16,24 forward and reverse x translation Ux=+/- .08/N;
N16 stationary U=0; N16 forward with additional centre-x offset .5 LU. R=N/5,
centre0=[N/2+.13+phase,N/2+.17,N/2+.19]. Run N^2 steps. Initial fluid is
equilibrium at rho=1,u=U. dx=1/N, dt=1/N^2 keeps physical box, sphere, speed
and duration fixed. Relative-flow Reynolds number is ZERO. Domain-size effects
for nonzero drag cannot be assessed here. Maximum 8 cases, 13824 cells and 576
steps/case, 180-second flow cap. Set BLAS thread count=1 for bounded CPU cost.

Exact continuum solution: spatially uniform rho=1,u=U, zero net force/torque on
the co-moving sphere; physical solid and fluid volumes constant. Numerical binary
fluid-node count is recorded, not assumed constant. All 113 prior unit tests plus
new sphere geometry, reflection, scalar traversal and complete-step tests run.

Separate diagnostics:
- Full-step mass/momentum ledger: pre/post fluid totals, collision defect,
  boundary incoming-outgoing mass and lab-frame momentum exchange, exposed/
  covered population totals. Normalize residuals by initial fluid mass.
- Actual global fluid mass drift (not just the balanced ledger).
- Binary-volume prediction: at uniform rho, Delta M equals Delta fluid-node count.
  Subtracting this for diagnosis does NOT repair conservation or pass its gate.
- Boundary-only impulse and boundary+status impulse candidate. A complete ledger
  is NOT proof that status-change bookkeeping is a physical hydrodynamic force.
- Boundary and status torques about the old centre, as diagnostics. No global
  angular-momentum closure claim: periodic angular flux is not audited here.

Predeclared gates: positive finite fluid, zero solid; max |rho-1| and |u-U|<=1e-10;
per-step normalized mass/momentum ledger residual <=1e-12; max global relative
mass drift<=1e-6; max absolute net boundary+status impulse<=1e-9 LU. Save failed
gates without modifying thresholds. Boundary-only zero-force and binary-volume
residuals are separately reported so compensating errors cannot hide. First and
final states and one complete cover/uncover step per moving case are archived;
every-step history includes centre, node counts, balances, forces and health.

Even a pass would qualify only this uniform-flow numerical benchmark, not sphere
drag or fibre release. If volume/force gates fail, stop promotion and identify the
needed volume representation/force formulation instead of applying a correction
chosen solely to make totals match.

Primary context inspected 2026-09-08: Peng et al. (2016), DOI
10.1016/j.camwa.2015.08.027, sections 4-5 discuss status-change force fluctuations
and refill/voxel-count issues. Our first-intersection geometry and explicit POST
implementation are verified separately, not claimed as a replica of their solver.
https://research.me.udel.edu/lwang/reprints/Peng_etal_CAMWA_2016.pdf
