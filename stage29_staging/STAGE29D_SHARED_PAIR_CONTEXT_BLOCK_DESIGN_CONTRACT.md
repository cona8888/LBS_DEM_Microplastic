# Stage29d shared-pair context-block mechanics design

Stage29c showed that the frozen pore-path library cannot supply three independent crossing pairs. Stage29d separates what can and cannot be replicated:

- one frozen two-fibre `crossing_pair` is the contact mechanism;
- one frozen two-fibre `separated_pair` is its zero-contact control;
- three source-distinct `context_pairs` provide two additional non-contacting fibres each;
- within each block, exactly the same context pair is combined with the crossing pair and the separated pair.

Thus A, B, and C are **context blocks**, not independent crossing-pair replicates. The paired contrast estimates whether the already-qualified contact mechanism remains distinguishable when two more separated fibres occupy different pore contexts. It does not estimate population variability of crossing locations.

All six non-intended pairs in each four-fibre case must remain separated under the sampled mechanical loading path. The contact case must have exactly one intended predicted and terminal contact edge; the control must have zero. Source paths for context fibres must be disjoint across A, B, and C.

This contract authorizes design generation and independent audit only. Geometry, runner, YADE, flow, and permeability claims remain unauthorized.
