# DEM engine decision for the permeability study

## Current MatDEM result

The attempted native runner was launched in MATLAB R2024b rather than a runtime
exposing MatDEM `pore3d`. Two independent limitations were reported:

- `pore3d` is not visible, so the native hydraulic network cannot be created;
- `gpuDevice` is unavailable, so GPU execution is not available through this
  MATLAB installation.

The initial `fs.randSeed` crash was an implementation error: MatDEM interpreted
the large calendar-style seed as an array dimension. The configuration now uses
seed 1, following the installed MatDEM examples. The runner also stops before
particle generation when either native capability is absent.

## Chrono options

### Chrono::DEM

Chrono::DEM is an open-source CUDA/HIP solver for very large sphere assemblies.
Its current official documentation limits the solver to monodisperse spheres.
That limitation conflicts with this study's 0.60--1.18 mm sand grading and
0.246 mm microplastic inclusions.

### DEM-Engine

Chrono's external DEM-Engine supports particles represented by clumped spheres,
varied sizes and shapes, customizable contact laws, and up to two GPUs. It is a
better match for the granular skeleton and the available RTX 4080 SUPER than
the monodisperse Chrono::DEM module. It does not provide a turnkey saturated
pore-network permeability calculation.

### Chrono::FSI-SPH

Chrono::FSI-SPH provides GPU SPH fluid dynamics and force/state exchange with
rigid and flexible bodies. Fully resolving water around approximately 95,800
grains and smaller plastic particles would require a much finer fluid marker
resolution than the DEM and is likely to be substantially more expensive than
a pore-network model. It should be treated as a high-fidelity benchmark for a
smaller domain, not the first application-scale model.

## Recommendation

Use the following hierarchy:

1. Give MatDEM one final capability check in the actual standalone application.
   Continue only if both `pore3d` and GPU support are exposed.
2. If either remains unavailable, move the DEM skeleton to Chrono DEM-Engine.
3. Export equilibrated particle positions and radii to a transparent 3D pore
   network or voxel-flow solver for clean and fixed-microplastic permeability.
4. Add two-way coupling only after the fixed-bed flow and force-transfer
   benchmarks pass.
5. Reserve Chrono::FSI-SPH for a reduced-domain resolved-flow comparison.

This route preserves GPU acceleration for the expensive contact problem without
pretending that Chrono automatically supplies the geotechnical permeability
physics that MatDEM `pore3d` was intended to provide.
