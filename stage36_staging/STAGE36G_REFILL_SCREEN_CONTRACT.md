# Stage36G: isolated moving-mask refill falsification

Question: can a small, positive, local population redistribution preserve fluid
mass AND avoid disturbing a uniform co-moving field during a binary-mask change?
This is a CPU FP64 algebraic mask-transition test, not a time-integrated flow or
force benchmark. No collision, streaming, moving-wall impulse, rigid-body motion
integration, soil, or release is simulated. Displacements below are geometric
snapshots, not time steps. No production solver or accepted evidence is modified.

Compare two explicit candidates:

1. AE6: average 2*f(x+d)-f(x+2*d) over available two-point retained-fluid rays in
the six Cartesian directions. Retained populations are unchanged; covered cells
are zeroed. This is a six-ray adaptation of averaged extrapolation, not a full
reproduction of a published moving-boundary method. Reject if no ray exists or
if any new population is nonpositive. No clipping or mass correction.
2. POOL6: covered-cell populations are split equally among face-adjacent retained
fluid cells. Each retained cell then shares its resulting populations equally
between itself and all face-adjacent newly exposed cells. Both phases use frozen
source arrays (no order-dependent in-place cascades). Each transfer edge has length
one lattice spacing. No global reservoir, density rescale, or transfer through a
persistent solid cell. Reject any changed cell without a retained face neighbour.
This deliberately simple project candidate is NOT attributed to a published method.
It conserves each population globally and is positive, but neither correct local
pressure nor angular momentum conservation follows from that property.

Each transfer archives source, destination and all 19 transferred populations.
Independently reconstruct the output from the ledger. Report orbital angular
momentum change; do not hide it by applying a fictitious body torque.

Frozen cases: cubic grids N=16,24,32; cell centres index+0.5; sphere radius N/5,
initial centre [N/2+.13,N/2+.17,N/2+.19]; translate along x by 0,.25,.5,1 LU.
Analytical solid volume is invariant. Its binary voxel count need not be invariant
for fractional translations. Initial fluid has rho=1, u=[.01,0,0] LU, full D3Q19
equilibrium populations. Initial and final sphere masks are archived with states.
At most 24 trials, 32768 cells/trial, CPU only. Also run all prior 81 unit tests.

Screen gates (fixed before execution): positive finite populations; exactly zero
solid populations; relative fluid mass change <=1e-12; max relative density
deviation from 1 <=.01; max velocity deviation <=1e-10 LU. POOL6 additionally
requires max per-population relative total change <=1e-12 and ledger reconstruction
error <=1e-13. Untouched far-field populations must match exactly. Unit tests check
invalid input, unsupported isolated transitions, locality, independent scalar
reconstruction, coordinate-origin effects and affine-population AE6 reconstruction.
No tolerance is tuned after results. A successful test harness does NOT mean a
candidate passed physical-fidelity gates. Preserve failed candidates and all trials.

Interpretation constraint: at uniform rho, binary fluid mass equals rho times the
fluid-node count. If that count changes, exact uniform density and exact mass cannot
both hold for a mask-only update without another flux/volume representation. This
is a diagnostic of the isolated update, NOT proof that complete published boundary
schemes fail. Streaming and boundary exchange must be audited in the same complete
step before judging total conservation or physical force.

Primary literature inspected 2026-09-06:
- Peng et al., Computers & Mathematics with Applications 72 (2016) 349-374,
  DOI 10.1016/j.camwa.2015.08.027, section 5.1.1 equations 48-49 (extrapolation),
  section 5.2 (separating refill and boundary-discretization effects).
  https://research.me.udel.edu/lwang/reprints/Peng_etal_CAMWA_2016.pdf
- Phys. Rev. E 86, 026701 (2012), abstract: local mass constraints can produce
  incorrect flow and pressure even though conservation sounds desirable.
  https://journals.aps.org/pre/abstract/10.1103/PhysRevE.86.026701

Next gate, not run here: complete prescribed moving-boundary CPU benchmark with
collision/streaming/boundary exchange/refill in one step, first constant-volume
planar translation then curved motion, checking pressure, force, and mass versus
resolution. No release campaign until that gate and outlet/contact gates pass.
