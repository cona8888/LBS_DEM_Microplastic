# Stage36C: rigid bent-fibre outlet accounting

Scope: manufactured geometry and bookkeeping verification only. No fluid solver,
DEM engine, physical transport trajectory, soil pilot, or validation claim.

Represent a fixed centreline as the geometric UNION of constant-radius capsules.
Do not add segment volumes: adjacent capsules overlap. Sample this union once on
a deterministic midpoint grid in the local frame. Each accepted sample has a
persistent index and equal share of a separately specified physical body mass.
Report the raw quadrature volume; mass normalization must not hide volume error.
This is a volume discretization, not material mechanics at capsule joints.

Transform the same sample cloud by proper rigid rotations and translations.
Changing curvature, fragmentation, variable radius, contact, self-intersection
physics, and remeshing are excluded. Only fixed bent shapes are covered.
Samples exactly on an inlet/outlet plane are inside. Full-body exit instead uses
the exact capsule-union support bound: minimum transformed centreline x minus
radius >= outlet. A sampled cloud alone cannot establish full exit.

Compare each persistent sample's endpoint category to count outward and returning
mass separately. Changes in total outside mass are NOT gross outward crossings.
Snapshot counting misses excursions between observations: it gives endpoint-
resolved crossing lower bounds, not time-resolved flux or unique release.
No event time, effluent concentration or retention mechanism is inferred here.

Predeclared manufactured-test gates:

- Inventory and signed crossing closure: relative error <= 1e-12.
- Straight capsule finest-grid raw volume relative error <= 0.01 and maximum
  tested plane-fraction absolute error <= 0.005, against analytic capsule values.
- Centred oblique straight capsule outlet fraction error <= 0.005 versus symmetry.
- Bent-shape CPD32-to-CPD64 raw-volume relative shift <= 0.01 and tested outlet
  fraction shift <= 0.005. These are refinement checks, not an exact bent reference.
- No assumption of monotone voxel convergence; report all CPD16/32/64 values.
- Collinear subdivision and repeated capsule segments must not double-count.
- Reject nonfinite input, zero-length segments, invalid rigid transforms, changed
  sample-array size, bad boundaries, nonpositive mass and oversized grids.
- Run all 25 Stage36B regression tests without modifying their sealed sources.

Bounded CPU-only fixtures; maximum 4 million candidate grid cells per cloud.
All outputs go to a new immutable directory; existing output directories are refused.
Passing permits preparation of a single-body fluid-force verification benchmark,
not soil flushing or physical release predictions.
