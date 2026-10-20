# Stage36E: body-resolved static bounce-link extraction

CPU-only manufactured-state verification. No collision/streaming steps, GPU
initialization, physical trajectory, original-flow replay or validation claim.
Keep every existing solver, geometry and result immutable.

Input: D3Q19 shifted FP32 populations g=f-w, uint8 phase (0 fluid, 1 sand,
2 fibre), separate nonnegative integer owner map (0 fluid, positive body ID),
and one unwrapping anchor per body. Phase alone is NOT a body identifier.
Array ordering is [q,z,y,x]; cell centres are (x+.5,y+.5,z+.5) lattice units.
Boundary mode is triply periodic ONLY. Maximum 262144 cells and 200000 links.

For a fluid destination with solid source at destination-cq, extract one link:
F_shifted=-2*g_opp*cq; F_baseline=-2*w_opp*cq. These are fluid-on-solid
momentum-exchange impulses per one lattice time step (force in lattice units).
The midpoint is destination centre-cq/2. Use the supplying solid cell's body
owner, not the destination's owner. Unwrap midpoint about the body's fixed
anchor, then take torque about that anchor. A later torque-origin change must
use T_new=T_old-(new-old) cross F without reselecting periodic images.

Preserve baseline and shifted components separately. Baseline is the reference
population contribution, not a full pressure/viscous decomposition. Do not label
the entire shifted contribution viscous drag. No moving-wall correction,
open outlet, newly exposed-cell repopulation or SI fluid calibration is included.

Each body must be a compact image representable about its declared anchor;
minimum-image ties at half a box are rejected. This API does not prove body
compactness or determine geometric ownership at contacts. External walls and
ambiguous overlap phase 3 fail closed.

Predeclared verification:

- Recover 4704 links for archived sphere_D16_L4_c000_f1p0 after checking its
  manifest-bound mask, record, audit files, qualification and source hashes.
- Compare link identities and body-wise force/torque against a separately
  written solid-centred scalar traversal (no np.roll and no extractor calls).
- Uniform reference state: closed sphere/body net force and torque exactly zero.
- Single-population pulse: force and lever-arm sign match the hand expression.
- Seeded small-domain states: body ownership, multiple bodies, periodic seam,
  global-origin torque accounting and reversal/linearity agree.
- Force/torque discrepancies <= 1e-12 relative to sum-of-absolute-link-component
  scales (floored at 1 LU for force, 1 LU^2 for torque); exact link counts/IDs.
- Reject mismatched owner maps, unknown IDs, nonfinite or nonpositive
  reconstructed populations, nonzero solid states, wrong dtype/shape, and
  oversized arrays or unsupported boundaries. Rerun all 61 previous unit tests.

The archived sphere directory has aggregate histories and final-state hashes,
not the final population array. Manufactured g arrays cannot recover that
original flow; record manufactured arrays/hashes separately and never compare
their drag with the archived converged drag as a physical benchmark.
