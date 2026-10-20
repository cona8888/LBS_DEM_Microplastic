# Stage36I — controlled boundary time-level diagnosis

CPU only; preserve Stage36H and its failed shear_N8 case unchanged. Compare H's
q>.5 incoming OLD population against POST-collision incoming population. The
q<=.5 formula, BGK collision, geometry timing, extrapolation refill, wall speed,
force/mass accounting, initial condition and thresholds are unchanged. This is
an algorithm verification change, not a physical parameter calibration.

Analytical falsification before flow interpretation: for linearized stationary
Couette flow ux=gamma*y, tau=.8 and wall ux=0, manufacture
f_k(y)=w_k*(1+3*c_kx*gamma*y)-3*tau*w_k*c_kx*c_ky*gamma.
Its post-collision value replaces tau by tau-1. A bottom-wall incoming value at
y=q must reproduce f_k(q). The POST variant reproduces this identity; the OLD
variant introduces the term -(2q-1)/(2q)*3*w_k*c_kx*gamma for q>.5. Test q=.25,
.5,.75,.9 and gamma=1e-4. This is a linearized boundary identity only; the full
flow solver continues to use quadratic D3Q19 equilibrium.

Reference context: Peng et al. 2016, DOI 10.1016/j.camwa.2015.08.027, equations
13/15 motivated H's original implementation. The incoming-symbol time level in
that presentation was used literally in H. Here distinguish pre/post explicitly
and use the analytical identity rather than interpreting notation as proof.
Official lbmpy interpolation documentation was also located (2026-09-08):
https://pycodegen.walberla.net/docs/lbmpy/2.0/notebooks/demo_interpolation_boundary_conditions.html
No lbmpy engine is installed or run; no exact published-code reproduction claimed.

Frozen 36 flow conditions: both OLD and POST variants on H's same 12 conditions
(N8,16,32 uniform, static shear, moving shear; N16 reverse movement, reverse
shear, rest). Then each variant on N8 and N16 moving shear with three additional
initial offsets +.25,+.5,+.75 LU relative to sqrt(2)/10. Thus wall-phase effects
are paired, not confused with algorithm differences. At most 36 CPU runs,
10240 steps per run, 120-second total flow cap. No new production or GPU jobs.

Reuse all H gates verbatim: 2% final ux normalized error; 5% cycle-averaged shear
error; 1e-6 global relative mass drift; 1e-11 operator ledger residual; density
and uniform-flow, normal velocity, normal traction and volume gates unchanged.
Add diagnostic late-window maximum profile error (not a replacement or a tuned
gate). Preserve phase failures even if the original failing phase improves.
Each late-window contains five complete mask crossing cycles as in H.

OLD phase-zero states must match H's archived final states exactly. All 105
previous unit tests run unchanged plus eight new time-level/domain tests.
Source/artifact hashes and per-case histories, initial/final/event states saved
to a new immutable output. All history budgets and final profiles rechecked from
saved artifacts. A source-level scalar comparison is NOT independent solver
validation. Diffusive refinement is not independent time/space convergence.

Decision: a correct boundary identity plus improved static controls can localize
one defect. It does not prove all moving-wall timing/refill errors are removed.
No arbitrary density repair, moment compensation or changed accuracy threshold.
No curved-fibre motion, release, wet contact or outlet qualification follows.
