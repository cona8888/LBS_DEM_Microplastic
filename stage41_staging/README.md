# Stage 41 optimized transport

Use `trajectory_optimized_v1.integrate` with
`geometry_exact_v1.GrainGeometry.from_geometry(existing_geometry)` for fixed
grains. The trajectory explicitly imports the optimized geometry and contact
solver; it does not replace globals in the historical solver modules.
Physical arguments and timestep controls retain Stage 40 conventions.
`stop_on_trap=False` is the default: a finite dwell never implies permanent
retention. `stop_on_trap=True` measures an explicitly censored finite dwell event.

Reproduction from `C:\MATDEM_MICROPLASTIC`, using Python with NumPy and SciPy:

```powershell
python stage41_staging/verify_contact_optimization_v1.py --output stage41_evaluations/contact_new
python stage41_staging/verify_geometry_exact_v1.py --output stage41_evaluations/geometry_new
python stage41_staging/verify_trajectory_optimized_v1.py --output stage41_evaluations/manufactured_new
python stage41_staging/verify_trajectory_optimized_v1.py --matrix --fractions 0.025 0.0125 0.00625 --output stage41_evaluations/replay_new
python stage41_staging/verify_trajectory_optimized_v1.py --profile --output stage41_evaluations/profile_new
```

Each output directory must be new. The last command runs baseline and candidate
sequentially on the original packing-2 AR4 start for 0.02 pore volumes; it is a
cost comparison at historical controls, not a convergence-qualified release
prediction. `--matrix` replays the archived difficult three-grain state for
0.02 seconds at three refinements and both friction values. Full trajectories
and verification summaries, dependency versions, transitive source hashes and
input hashes are saved. Timestep refinement changes both displacement and
relaxation controls in a fixed 1:5 ratio; this does not independently isolate
those controls or prove a formal order of convergence.

Read the [review](../stage41_evaluations/ALGORITHM_REVIEW.md) and
[research contract](../stage41_evaluations/RESEARCH_CONTRACT.md) before using
results for inference. More expensive refined motion can be necessary even
though the implementation is faster. A single packing/state is not a replicated
study, and the original rotating-sweep search remains numerically checked rather
than mathematically certified for arbitrary motion.
