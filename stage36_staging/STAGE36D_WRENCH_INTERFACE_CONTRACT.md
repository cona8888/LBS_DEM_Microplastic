# Stage36D unit-interface scope

Implements the manufactured-wrench rung of the existing Stage36D benchmark
contract. Inputs are known force/couple samples, not inferred water forces.
CPU only. No engine imports, installations, GPU kernels or fluid/DEM steps.

One body per map, unwrapped Cartesian positions in metres, fluid-on-body force in
newtons, intrinsic couples in newton-metres. Node arrays require rotational DOFs.
The caller provides host-node pairs and attachment fractions; ownership/nearest
surface selection and periodic unwrapping are NOT inferred by this component.
Array order is binding. Rebuild and reverify the map if geometry/order changes.

For each source sample at xs carrying force f and intrinsic couple c, transfer
to host node j at xj with weight wj:

    fj += wj f
    cj += wj [c + (xs-xj) cross f]

The weights of the two host nodes sum to one. Therefore both net force and torque
about any common origin are preserved. The velocity interpolation is the work-
conjugate operator: vs = sum wj[vj + omega_j cross (xs-xj)] and
omega_s = sum wj omega_j. Hence source and nodal instantaneous power agree.
This is a discrete work-conserving map, not a validated flexible beam interpolation
or proof of coupled time-integrator energy conservation.

Do not discard nodal couples: transverse offset forces and axial spin torque
cannot generally be represented by a force-only map on collinear nodes.
Do not reconstruct a unique load distribution from total force/torque alone.
Source pressure/viscous/body-force separation is the upstream solver's job.

Predeclared checks (threshold inherited from Stage36D): errors <= 1e-12 after
scaling by nonzero force 1e-9 N, torque 1e-12 Nm and power 1e-12 W for the
manufactured SI fixtures; use corresponding rescaled references for unit checks.
Check zero loads, known lever arms, pure couples, origin/frame changes, equal and
opposite fluid reaction, power conjugacy, rigid-body velocity reproduction,
nonuniform nodal velocities, superposition, shared-node accumulation and unit
rescaling. Negative tests reject invalid topology, weights, shape/nonfinite loads,
overflow and a receiver without explicitly declared nodal-couple capability.

Run the 41 previous Stage36B/C unit tests unchanged as regressions. Preserve parent
verification hashes and all audited engine-source excerpts. A passed unit suite
does not pass sphere drag, rotation, moving-boundary conservation, or soil release.
