# Stage36M — separate time-scale and surface-marker refinements

Bounded CPU solution-sensitivity check, not drag validation or fibre release.
Preserve Stage36L; same endpoint-impulse scheme and physical nonuniform test.
Fixed physical box1, radius.2, rho1, nu.1, U=(.08,0,0), perturbation
ux=.02*sin(2*pi*y), physical end time1. Fixed N16, dx1/16.

Time-scale levels s=1,2,4: dt=1/(256*s), tau=.5+.3/s, lattice U=.005/s,
perturbation amplitude=.00125/s, steps256*s. Fixed marker count56.
This holds physical nu=(tau-.5)/3 *dx^2/dt constant. Acoustic speed and Mach
also change, so this is fixed-grid LBM time-scale/relaxation sensitivity,
NOT a clean independent temporal order of the incompressible equations.
Marker levels32,56,80 at s1; fixed independent256 off-marker probes for all.
Fibonacci clouds are regenerated with count, not nested; no marker calibration.
Five unique immersed cases (shared56,s1 baseline); baseline must reproduce L
initial/final arrays exactly. Three unforced periodic shear-decay controls s1,2,4
compare projection amplitude against exp(-nu*(2*pi)^2*t), max amplitude error
normalized by initial amplitude<=.02. No sphere in these three controls.
Maximum8 flow cases,1024steps/case,N16; CPU flow cap180 seconds.

All141 regression tests plus new unit/scaling tests before execution. Full fields
at physical times .25,.5,.75,1 and first-step packet. Every-step balances/slips.
Same L gates: total mass drift<=1e-10; exterior geometric mass estimate drift<=1e-6;
normalized momentum ledger<=1e-12; marker slip<=1e-10 LU; density error<=.01;
off-marker slip/initial amplitude<=.05; final quadrature discrepancy<=1e-6.
No clipping, pinv, regularization or threshold relaxation. Condition cap1e10.

Conversions: velocity_phys=u_lu*dx/dt; force_phys=F_lu*dx^4/dt^2;
body impulse_phys=sum F_lu*dx^4/dt. Here force scale multiplier=s^2 and impulse
multiplier=s/256. F_lu is the per-step force candidate including interior momentum,
not independently validated hydrodynamic traction. Never compare raw LU forces
between different s levels.

Comparisons use common physical quarter-time fields. Report pairwise max quarter-time
RMS vector velocity difference divided by initial perturbation amplitude .02.
Impulse-history differences at common coarse endpoints are normalized by rho V*.02.
Late force comparison uses averages over each baseline dt interval (all fine-step
impulses included), physical times [.25,1], normalized by 6*pi*nu*R*.02.
This reference force scale is dimensional normalization, NOT an assumed measured drag.
Fine-pair gates: field difference<=.02; impulse-history difference<=.02;
late force difference RMS<=.02, and each fine-pair error smaller than coarse-pair.
Time pairs1->2,2->4; marker pairs32->56,56->80. No formal order for marker spacing.
Exact agreement can be reported as roundoff-limited rather than strict improvement.
If any gate fails, retain failure and stop promotion; assess whether the observable
or discretization needs a bounded diagnostic before a physical sphere-drag benchmark.
