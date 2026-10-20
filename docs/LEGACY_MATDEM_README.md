# MatDEM Microplastic Permeability

Research code for studying how microplastics change the permeability of sand using MatDEM and MATLAB.

## Current scope

The first executable is a mechanism-neutral, two-pore pressure-equilibration
toy. The installed MatDEM distribution does not expose
the `pore` or `pore3d` classes, so the hydraulic toy currently uses a clearly
labelled reduced two-reservoir model. It checks storage balance and compares
the numerical pressure decay with its analytical solution.

The study will cover both immobilized and mobile microplastics. These are kept
as separate fidelity stages: fixed inclusions first alter packing and the pore
network; a later transport stage adds release, migration, throat retention and
time-dependent clogging. The research interview still needs to define the
permeability-test protocol, particle properties, mixture definition and
validation data.

The next executable stage is a transparent reduced mechanism study. Fixed
spherical inclusions modify the mixture specific surface in Kozeny-Carman;
mobile particles follow a retained-mass balance with attachment, detachment,
finite capacity and permeability loss. It is a hypothesis and calibration
tool, not a MatDEM `pore` prediction.

The active case is a saturated 50 mm diameter by 20 mm high cylinder filled
with Leighton Buzzard sand, Fraction B. Literature inputs are D10 = 0.65 mm,
D50 = 0.82 mm, Cu = 1.38, emin = 0.46 and emax = 0.79. A declared medium-dense
scenario, Dr = 50%, gives e = 0.625 and porosity = 0.3846. Both constant-head
and falling-head equations are executed. The constant-head gradient and
falling-head standpipe/head levels remain explicit toy assumptions until the
laboratory apparatus is specified.

The microplastic is currently represented as a generic sphere with diameter
0.30 D50 = 0.246 mm. The run contains a clean comparator and one 1% plastic
solid-volume mixture. The polymer, shape, content and mobile-retention
parameters are uncalibrated placeholders and are not literature claims.

## External dependency

The MatDEM installation remains read-only at:

```text
C:\Users\wonjuncha-admin\Downloads\MatDEM\MatDEM5.00(Win&Linux)
```

The setup function adds only the required project and MatDEM directories to the active MATLAB path. It does not copy or edit MatDEM files.

## Run the toy

In MATLAB R2024b:

```matlab
cd('C:\MATDEM_MICROPLASTIC')
run('scripts\run_two_pore_toy.m')
```

Expected evidence is `TWO_PORE_TOY_PASS`. It records the selected hydraulic
backend, decreasing pressure difference, storage balance and analytical error.
Results are written under `runs\toy_two_pore`. The native two-ball diagnostic
is excluded from the default run because the protected MATLAB-side `balance`
path currently opens a modal and does not advance physical time.

Run the test with:

```matlab
cd('C:\MATDEM_MICROPLASTIC')
results = runtests('tests\test_two_pore_toy.m');
assertSuccess(results)
```

Run the reduced fixed/mobile study with:

```matlab
cd('C:\MATDEM_MICROPLASTIC')
run('scripts\run_microplastic_reduced_study.m')
```

It writes a MAT result, JSON summary, fixed-inclusion CSV, hydraulic-protocol
summary, and constant-/falling-head mobile time histories under
`runs\leighton_buzzard_fraction_b_dr50_mp_ratio_0p30`.

## Native 3D hydromechanical model

A staged native MatDEM `pore3d` model is prepared for the same 50 mm by 20 mm
Leighton Buzzard Fraction B specimen. It resolves the reconstructed sand
grading from 0.60 to 1.18 mm, includes 1% fixed spherical microplastic by solid
volume, constructs a three-dimensional pore network and enables two-way
pore-pressure/particle-force coupling. The resolved assembly has approximately
95,800 physical particles.

Run it inside the standalone MatDEM application from its MATLAB command/editor
environment:

```matlab
cd('C:\MATDEM_MICROPLASTIC')
run('scripts\run_native_matdem_hydromechanical_case.m')
```

The three stages can also be run separately using
`native_matdem_prepare_specimen`, `native_matdem_initialize_pore3d`, and
`native_matdem_run_coupled_permeability`. See
`docs\NATIVE_HYDROMECHANICAL_MODEL.md` before running. The native model is
prepared and statically verified, but has not yet completed a native `pore3d`
run. Contact properties and the throat-flow factor are calibration parameters,
and microplastics are fixed inclusions rather than transported particles.
The execution script stops before particle generation if `pore3d` or GPU
support is unavailable in the active runtime.

## Restricted-session control bridge

If an external client cannot discover a MATLAB shared-engine session, start
the project-local bridge once inside the licensed MATLAB Command Window:

```matlab
cd('C:\MATDEM_MICROPLASTIC')
addpath('src')
start_codex_matlab_bridge
```

The bridge polls `control\inbox` once per second and writes structured JSON
responses to `control\outbox`. It accepts only the whitelisted actions
`probe_environment`, `probe_matdem_capabilities`, `reload_project_functions`,
`run_reduced_hydraulic_toy`, `run_matdem_core_toy`, `run_two_pore_toy`,
`run_microplastic_study`, `run_project_tests`, and `stop_bridge`; request
files can never supply arbitrary MATLAB source for
evaluation. Processed requests are preserved under `control\processed`.

## Confirmed local limitations

- MatDEM core `fs`, `mfs`, `build`, and `obj_Box` components are installed.
- MatDEM `pore` and `pore3d` implementations are absent from the visible
  distribution, although example scripts that call them are included.
- MATLAB and Simulink are installed. The Parallel Computing Toolbox licence
  test succeeds, but the toolbox product files and `gpuDevice` are absent;
  current runs therefore use CPU.
- The supplied MatDEM 5.0 package is a standalone `MatDEM.exe` application
  built for MATLAB Runtime R2023b. Directly driving its protected p-code from
  the shared MATLAB R2024b session failed in `basicfs.saveRecord` on its first
  direct call. A later diagnostic started with `dT = 1e-4 s` and nonzero
  gravity, but the protected `balance` path opened a modal and returned with
  `dT = 0`, `totalT = 0`, and no particle motion. No native/GPU verification
  pass is claimed from MATLAB. The standalone MatDEM application is left
  available for native GPU work.
- The host has an NVIDIA GeForce RTX 4080 SUPER with 16 GB VRAM. Hardware is
  suitable for MatDEM GPU trials once the standalone runtime path is used.

## MatDEM reference examples

The project is based on these unmodified MatDEM 5.00 examples:

- `examples2019\user_L3PorePermeability1.m`: specimen generation and sedimentation.
- `examples2019\user_L3PorePermeability2.m`: hydraulic material assignment and equilibration.
- `examples2019\user_L3PorePermeability3.m`: pore construction, applied head, steady flow, and hydraulic-conductivity calculation.
- `examples2018\user_TwoBalls.m`: minimal native MatDEM mechanics integration.
- `examples2021_22\user_TwoPore.m`: target `pore3d` pressure equilibration;
  unavailable with the current distribution.
- `examples2021_22\user_Pore3dCoupleTest1/2/3.m`: three-dimensional fluid-solid coupling.

See `docs\RESEARCH_CONTRACT.md` for the decisions required before implementing the full mixture model.
The reduced-model equations, verification evidence and claim limits are in
`docs\REDUCED_MODEL.md`.
