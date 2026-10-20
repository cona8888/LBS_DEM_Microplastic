# Stage36F: planar moving-wall verification and cell-change audit

Two deliberately separate components:

1. A small CPU FP64 BGK D3Q19 Couette solver, homogeneous in x/z, resolving y.
   Fixed planar walls at y=0,H slide tangentially. No changing mask or particle.
   This is NOT the production FP32 projected CUDA solver.
2. A manufactured fluid-cell cover/uncover balance audit, without a refill law.
   It reports mass change and the impulse/angular impulse needed to account for
   removed/added populations. It rejects uncompensated mass change. Recording a
   compensating impulse is not proof that a dynamics solver applied it.

Moving-wall rule in the incoming direction c_q (wall -> fluid):

    f_in = f_out + 6*w_q*rho_wall*(c_q dot u_wall)
    J_on_wall = -(f_out+f_in)*c_q

Use fixed reference rho_wall=1, lattice cs^2=1/3, tau=.8 and nu=.1. FP64 rational
weights are used, not the stored FP32 weights. Zero wall velocity reproduces
stationary reflection exactly. This lab-frame impulse bookkeeping is not a
general Galilean-invariant moving-body hydrodynamic-force implementation.

Primary method description inspected 2026-09-06: Greiner, Pastewka and Wang,
Boundary conditions, moving-wall equation (4), with the opposite direction
convention: https://pastewka.github.io/Accelerators/lecture/boundary-conditions.html
Their tangential-wall case conserves mass; normal motion/change of fluid domain
needs additional treatment. The formula is adapted here to the D3Q19 weights.

Predeclared bounded runs: N=8,16,32 at U_top=.08/N, U_bottom=0. Thus H_phys=1,
nu_phys=.1, U_phys=.08 with dx=1/N, dt=1/N^2; refinements keep Re=.8 constant.
Start from rest. End at theta=nu*t/H^2=2 (20*N^2 steps), record theta=.1 and 2.
Compare transient u/U=s+(2/pi)*sum[(-1)^n*sin(n*pi*s)/n*exp(-n^2*pi^2*theta)]
and steady u/U=s. No pressure gradient. Additional N8 runs: zero, negative lid,
half lid, and both walls translating equally with matching initial fluid speed.
Maximum 7 flow cases, N<=32, 20480 steps/case, total wall-clock cap 120 seconds.

Acceptance: each-step fluid-momentum change plus both wall impulses <=1e-11
(absolute lattice units); relative fluid-mass drift <=1e-10; positive finite
populations. Final normalized profile max error <=1e-6; wall shear error <=1e-5
against rho*nu*U/H. Fine-grid transient normalized RMS error <=.003 and less
than .7 times the middle-grid error. These are project numerical gates, not
experimental uncertainty. Do not claim independent dt/dx convergence: this is
diffusive refinement. Record all results, including failures; no fitting of gates.

Cell-change audit: retained-fluid populations must be unchanged; covered cells
become exactly zero; new fluid requires supplied positive populations. For
each changed cell, J_body=P_removed-P_added and K_body=L_removed-L_added.
Check unwrapped-position angular impulse about a declared common origin. No
reservoir, global density rescaling or deletion of imbalance is permitted.

All prior 73 unit tests run unchanged. No GPU/DEM/YADE job, mobile sand, fibre
trajectory, soil transport or permeability-validation claim is authorized here.
