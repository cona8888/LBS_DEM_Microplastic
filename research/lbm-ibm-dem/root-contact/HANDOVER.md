# Dry root-contact integration: development review and fix

## A. Verdict
Verified within the bounded dry, prescribed-root fixture; experimentally unvalidated.
The repair removes a reproduced force-lag energy defect. It does not establish
flexible-root mechanics, living-root growth, or growing-root multiphase coupling.

## B. Inspected state and arrangement
Base remote: `60518bbef283f8ff3dcdb407bddcfc802d99be41`, branch
`feature/rhizofield-root-contact`, draft PR 1. Full local source baseline:
`03ee352240c6dd582d5d10b50e38ddb9f0d69a77` from the supplied RhizoField bundle.
Three lead-developer review passes covered LBM/coupling, root/soil mechanics,
and software/evidence. No independent subagents or external reviewers were used.

| Capability | Mechanism/source | Executable evidence | Status and limitation |
|---|---|---|---|
| Root contact geometry | Tapered endpoint-ball hull, `geometry.hpp`/`search.hpp` | `make test`, independent scalar oracle | Verified sphere/span geometry, not arbitrary CT surfaces |
| Dry soil | Native 2D spring/dashpot/Coulomb DEM | Native regression suite and growth fixture | Verified numerical cases, no natural-soil calibration |
| Root force integration | Symmetric root/native-DEM split, `stepper.hpp` | `make integration-test` | Verified within tests; contact switches still require timestep studies |
| Friction history | `traction.hpp::advanceHistory` | Slip, release, recontact, rollback tests | One material patch per strand; remeshing needs explicit remap |
| Root growth | Prescribed last-span extension, `growth_cell.cpp` | Five timestep levels and segmentation controls | Rigid kinematics; no EA/EI/GJ or biological driving law |
| LBM/IBM | Separate supplied v0.3 solver | Original core regressions passed locally | Not exercised in this dry root driver |
| Suction and uptake | Separate equilibrium capillary/hydraulic prototype | Existing 20 tests passed unchanged | Not continuously coupled to this growing root |
| Physical validation | Published calibration/DVC evidence register | No new experimental pair or force curve executed | Unavailable for this milestone |

## C. Findings
**High, reproduced defect:** old root loads were supplied as constant external
forces to native `DEM::advance`. That API intentionally holds external forces
constant; the state-dependent root caller was wrong. At 800 steps/period over
20 undamped periods, energy grew 63.8000%. At 200 steps/period it grew 619.695%.
Run `bin/integration_test` to reproduce held and corrected methods.

**Medium, reproduced defect:** duplicating a frictionless contact entry doubled
1 N/m to 2 N/m. `PlanarLaw` now rejects repeated identities before committing state.

**Medium, reproduced reporting limitation:** 101 saved samples missed true
per-step extrema. The finest sampled peak was 2.204523 N/m; actual per-step peak
was 2.213216 N/m. Running peaks and interval min/max are now recorded.

**Medium, reproduced reproducibility gap:** the remote source lacked the native
files needed by its demos. `native/` supplies three unchanged source files with
provenance hashes. No native DEM implementation was edited.

**Missing evidence:** flexible roots, prepared soil, coupled growing-root fluid
budgets and independent physical validation. Fast root search alone does not
accelerate the native all-pairs grain-grain loop or qualify full LBM performance.

## D. Changes
Half root kick, native grain-contact advance, one active-interval tangential
history increment, then refreshed endpoint root kick. Velocity-dependent loads
use an iterated midpoint kick. Failed iterations leave physical state unchanged.
Stable grain identities/topology are checked. Support forces are refreshed too.
Stiffness, density, friction and hydraulic calibration remain unchanged.
This is an established numerical-integration repair, not a new constitutive law.

## E. Verification matrix
| Case | Gate | Measured result | Status |
|---|---|---|---|
| Normal elastic oscillator | Max relative energy error <3e-4 at 200 steps/period | 2.46740135e-4 | PASS |
| Normal refinement | Observed energy/state order >1.8 | Approximately 2.00; energy error 1.54226e-5 at 800 | PASS |
| Tangential plus rotation oscillator | Relative energy error <3e-4 | 2.46740109e-4 | PASS |
| Damped oscillator, 200 steps/period | Displacement error/amplitude <0.002 | 1.574342e-4 | PASS |
| Midpoint-kick work identity | Residual/initial energy <1e-10 | Largest audited value 9.58e-12 | PASS |
| Search control | Direct/cached difference <1e-12 | Zero in all recorded columns, five timestep levels | PASS |
| Root segmentation | Force difference <0.1% for 2x/4x subdivision | Zero for unchanged tapered surface | PASS |
| Finest timestep comparison | Force samples/envelope <2%; true peak <1% | 1.37589%; 0.24692% | PASS |
| Static-root control | Motion and force <1e-12 | Zero | PASS |
| Axial/radial spring probe | Reaction relative error <1e-5 | Both recover 0.00990099 N/m | PASS |
| Safety/history | Duplicate, read-only queries, release, identity, rollback | All targeted assertions pass | PASS |

The original geometry tests, native core regressions and 20 application/
calibration tests passed. Address/undefined-behaviour sanitizers and warning-as-
error builds passed for the new integration suite. These are scoped tests, not
proof that every unsupported input or future topology change is safe.

## F. Validation
No calibration values were fitted and no independent experiment was run. The
published wet-bridge and CT/DVC data remain future held-out comparisons. Do not
call an analytical oscillator or a plausible grain-motion pattern validation.

## G. Demonstrator
56 disks (35 mobile, 21 fixed), grain diameter 0.5 mm, root tip diameter 0.54 mm;
ordered zero-stress geometry, not deposited/consolidated soil. Root extension
100 micrometres over 30 ms, followed by a 10 ms hold. Maximum imposed tip speed
5 mm/s is a manufactured loading rate, not biological time.
At dt=0.625 microseconds: true peak 2.213216 N/m at 32.971875 ms, final maximum
grain movement 67.7342 micrometres, final reaction 2.198841 N/m. The peak is in
the hold period: report a dynamic fixture reaction, not quasi-static impedance.
Accumulated kick-work residual 3.26472e-16 J/m is not a full independent audit of
all frictional dissipation. Fluid, permeability, suction and root bending outputs
are not applicable.

Five interleaved whole-driver timing repetitions at 16,000 steps: corrected
cached median 1.36084 s, corrected direct 1.70366 s, legacy held cached 0.699384 s.
Cached search is about 1.25x faster in this full corrected fixture. Correction
costs about 1.95x at the same timestep; the old scheme fails conservation and is
not an accuracy-matched competitor. No universal fastest-code claim.

## H. Reproduction and evidence
```
make test
make integration-test SOLVER=native
make bin/growth_cell bin/native_probe SOLVER=native
./bin/native_probe tip cached 6000
./bin/native_probe radial cached 6000
python3 run_review.py --output review_run
```
`run_review.py --resume` accepts only checksum-matching completed case outputs;
it reruns tests and timings. Aggregate execution-tool timeouts were handled by
split calls and this checkpoint, not relabelled as test passes.
GCC 14.2.0 C++17 -O3, Python 3.13.5, AMD EPYC 9V74, one thread, 4 GiB container
limit. `review/provenance.json` records native hashes; the full supplied review
archive includes raw histories, detailed A-I report, plots (CSV/Python/SVG/PDF),
source hashes, logs and local Git history. This remote module provides runnable
source plus compact evidence. Remote commit confirmation is separate from this
source document; nothing here asserts a merge into main.

## I. Next priorities
1. Prepare and equilibrate soil at defined density/confinement; qualify rate dependence.
2. Verify a flexible root against axial/cantilever tests before EA/EI claims.
3. Close moving-root fluid mass/momentum/volume budgets before wet-growth claims.
4. Freeze parameters and compare independent measured force plus displacement fields.
5. Profile grain-grain search and connect swept guards to rollback before larger steps.

Primary sources: LAMMPS timestep documentation
https://docs.lammps.org/Developer_flow.html ; Fakih et al. 2019 flexible root
https://doi.org/10.1103/PhysRevE.99.042903 ; resolved fluid/contact benchmark
sequence https://arxiv.org/abs/2003.01490 . These establish prior methods and
comparison requirements, not experimental support for this implementation.
