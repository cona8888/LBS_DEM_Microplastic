# Stage26f: robust four-support cage placement

## Physical question

Can two F37 microplastic fibres be inserted into the accepted 216-sphere LBS
packing with fresh, mechanically redundant sand support cages that are more
likely to survive fixed-fibre equilibration than the spent two-tip-contact
placements?

## Diagnosis being addressed

Candidates 01, 04, 05 and 07 all reused the same two anchor pairs.  Every fibre
had exactly two tip contacts.  Two frictional point contacts have a
rank-deficient six-DOF wrench system, so they are not a general rigid-body cage.
Three spent poses reached the temporal fixed-fibre gate and one did not; the old
static gates therefore did not generalize.

## Model boundary

- Sand state: accepted Stage25 216-sphere LBS packing and its frozen contact
  network.
- Microplastic geometry: rigid F37 kinked fibre, 37 overlapping 50-micrometre
  member spheres per fibre.
- Current stage: host-Python geometry generation and static screening only.
- No YADE execution, fibre release, rehydration, deformation, flow,
  permeability, migration or production parametric claim is authorized by this
  contract.

## Predeclared geometry gates

Each fibre must have:

- at least four distinct sand support bodies;
- support bodies in the accepted load-bearing core with network degree at least
  four;
- four distinct support member indices, including both tips and two interior
  locations separated by at least four member indices;
- frictional contact-wrench rank six and condition ratio at least 0.02;
- contact-normal span ratio at least 0.20;
- equal-normal-force residual at most 0.30 and equal-normal-moment residual at
  most 0.12, used as geometric balance proxies rather than calibrated forces;
- sand-fibre penetration no greater than 0.02 member radii;
- all member spheres inside the primary periodic cell.

The two fibres must use disjoint sand support bodies, have no overlap, and have
minimum initial fibre-fibre clearance at least 0.41129327255147165 mm.

## Freshness and independence

- Sand body IDs 6, 18, 40 and 119 used by the spent placements are excluded.
- Candidate08 is not read, evaluated or executed and remains reserved.
- Actual Stage26f geometries must use fresh support quartets and must not be
  selected from the exploratory feasibility probe.
- Geometry generation may use deterministic development seeds, but dynamic
  development/held-out allocation will be frozen only after static generation,
  independent audit and visual review.

## Falsification and stopping

Failure to find at least six admissible two-fibre geometries spanning at least
four distinct joint support topologies within the predeclared offline budget is
a geometry-design failure.  The budget will not be extended after inspecting
the outcome.  No YADE dynamics may begin from a failed static campaign.

