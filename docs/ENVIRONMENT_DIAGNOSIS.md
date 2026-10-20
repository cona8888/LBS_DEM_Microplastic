# MatDEM Runtime Diagnosis

## Confirmed environment

- MatDEM executable: version 5.0.0.0.
- MatDEM distribution: standalone compiled application with p-coded MATLAB
  support files and examples.
- Supplied installation instruction: MatDEM 3.80 and later use MATLAB Runtime
  R2023b.
- Shared development session: MATLAB R2024b with MATLAB and Simulink only.
- MATLAB `pore` and `pore3d`: absent as files, classes, and built-ins.
- MATLAB `gpuDevice`: absent because Parallel Computing Toolbox product files
  are not installed, despite a successful licence-entitlement test.
- GPU hardware: NVIDIA GeForce RTX 4080 SUPER, 16 GB VRAM, compute capability
  8.9, driver 581.42.

## Executed evidence

The project bridge successfully called MatDEM `build`, `material`, and
`setModel` after entering the MatDEM installation root. The five-particle
`CodexTwoBalls` model was announced by MatDEM. The first corrected execution
failed inside the protected `basicfs.saveRecord` / `basicfs.testTime` path
with `MATLAB:unassignedOutputs`. A subsequent structured diagnostic started
with `dT = 1e-4 s` and nonzero gravity (`mGZ = -12.3694` for both dynamic
particles). The protected `balance` path opened a modal, then returned with
`dT = 0`, `totalT = 0`, zero velocity, and unchanged coordinates. The native
probe is therefore excluded from the default MATLAB suite. Until a documented
API path advances physical time and the trajectory check passes, no native
MatDEM verification pass is claimed from MATLAB.

The MatDEM run also updated `XMLdata/boxsample.mat` as part of its internal
recording routine. The project code does not edit that file directly. It must
not be restored or replaced without explicit user authorization.

## Modelling consequence

The shared MATLAB session remains useful for project code, transparent
analytical checks, reduced pore-network verification, data analysis, design
generation, and calibration tooling. Native MatDEM CPU/GPU simulations should
preferentially be launched through `MatDEM.exe` and its R2023b runtime. A vendor-supplied
`pore3d` module or a separately verified geometry-to-pore-network adapter is
still required for three-dimensional permeability simulations.

Until those dependencies are available, reduced hydraulic outputs are code
verification only. They are not MatDEM permeability predictions and cannot be
calibrated or validated as the sand-microplastic application model.
