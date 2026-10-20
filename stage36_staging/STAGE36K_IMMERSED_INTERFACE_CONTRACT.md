# Stage36K — immersed-interface operators, not a flow solution

Question: can a fixed-lattice candidate transfer velocity/force and integrate
moving interior momentum without Stage36J's cell-count discontinuity?
Scope: CPU FP64 algebra and geometry only. No collision/streaming, time integration,
no-slip solve, drag, sand, fibres, release, rotation dynamics or production changes.
Stage36J remains failed. This is a new candidate, not a corrected Stage36J result.

Primary formulation sources inspected 2026-09-08:
- Peskin (2002), DOI 10.1017/S0962492902000077, eq.6.27: four-point regularized
  delta kernel; zeroth and first moments support conservative, adjoint transfer.
  https://www.cambridge.org/core/services/aop-cambridge-core/content/view/95ECDAC5D1824285563270D6DD70DA9A/S0962492902000077a.pdf/immersed_boundary_method.pdf
- Uhlmann (2005), DOI 10.1016/j.jcp.2005.03.017, eqs.9–11 and Appendix B eq.25:
  fixed-grid immersed forcing and interior-fluid momentum contribution to force.
  https://arxiv.org/html/1809.08170v1
  Uhlmann used a three-point kernel and a finite-difference solver; our four-point
  algebra test is neither a reproduction nor validation of that implementation.

Candidate: full computational fluid lattice, including fictitious interior fluid.
Keep computational total mass separate from exterior physical-fluid mass. A fixed
grid conserves neither exterior mass nor no-slip automatically. Interior integrals
must be evaluated consistently; do not assume rigid interior velocity in general.
For translation, no other body force: F_h = -F_IB + dP_inside/dt, with F_IB the
integrated force exerted on computational fluid. Additional external body forces
require a separately derived subtraction. Torque/rotating frames deferred.

Operators: J u = sum_i u_i w_il; S F = sum_l F_l w_il/h^3.
F_l is integrated marker force [N], not traction or force density. J and S use
identical unnormalized kernel weights, so h^3 sum u_i dot S F_i = sum J u_l dot F_l.
Grid positions x_i=(i+.5)h. Reject stencil support crossing the outer box; no
periodic torque ambiguity. No boundary weights clipped or normalized after creation.

Interior integration: positive tensor Gauss-Legendre r,mu and periodic theta
quadrature in body coordinates; r^2 Jacobian, radius .2 in unit box.
Persistent quadrature points translate with the body. Weight sum = analytic sphere
volume by quadrature construction, NOT a measured fluid-conservation result.
Deposited volume density is a smoothed indicator, NOT exact cut-cell occupancy.
Do not use it as a porosity field without further local consistency tests.

Frozen plan: N=12,16,24; nine shifts x/h from 0 to1 in increments1/8;
centre=((N/2-.4+phase)/N,(N/2+.17)/N,(N/2+.19)/N).
Volume quadrature 4 radial x8 mu x16 theta =512 points.
Deterministic force/velocity arrays seed3611, tests also h=.5 and h=1.
Check partition unity, first moments, constant/affine interpolation, total force,
torque and adjoint power. Absolute dimensionless residuals <=1e-11; relative volume
and centroid/moment errors <=1e-11. Density*volume integral in uniform fluid uses
rho=1. Interior momentum difference under constant acceleration compared with
rho V a; force extraction tested with independently prescribed nonzero F_h.
Quadratic-field interior integral against V*(centre^2+R^2/5): require monotonic
reduction in worst phase error for N=12,16,24 and observed order >=1.5.
Negative controls: omitted h^-3, wrong force sign, omitted interior momentum.
All121 prior unit tests must pass, plus new interface tests. No new flow runs.

Decision: passing qualifies only interface operators for a subsequent bounded
full CPU immersed-boundary sphere benchmark. Next benchmark must check actual
computational AND exterior mass, density, no-slip residual, force, time-level
consistency, nonuniform perturbations and refinement. Do not promote on uniform
co-motion alone, which can pass with an ineffective zero-force interface.
