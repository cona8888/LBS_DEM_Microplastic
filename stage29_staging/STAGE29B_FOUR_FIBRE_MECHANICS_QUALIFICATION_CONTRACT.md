# Stage29b four-fibre mechanics qualification design contract

## Purpose

Qualify whether four deformable F37 fibres can be embedded in the accepted fixed 216-grain LBS packing without invalid contacts, path drift, sand motion, or ambiguous topology. This is a mechanics qualification, not a permeability run.

## Paired topology design

Three blocks (A, B, C) each contain a matched pair:

- `low_contact`: four fibres, zero inter-fibre contact edges after the stable hold;
- `contact_rich`: four fibres, exactly two intended inter-fibre contact edges after the stable hold, forming two disjoint crossing pairs.

The paired geometries must use identical individual fibre contour length, radius, material, discretisation, and per-fibre orientation targets. Within a block, the centroid-distribution and orientation mismatch between topology variants must be reported and bounded before execution. No contact between the two intended crossing pairs is permitted.

## Construction strategy

Candidate paths are generated in the periodic cell from accepted Stage28a two-fibre path families, then transformed and screened geometrically. The preflight must measure clearances to sand and to all other fibres using periodic minimum-image distances. Topology is accepted only from measured terminal contacts, never from the requested label.

## Hard gates

- six unique cases and three complete matched blocks;
- four fibres and 37 centreline nodes per fibre;
- exact fixed sand coordinates and cell;
- zero false same-fibre contacts and zero cross-node bonds;
- complete intrafibre bonds;
- low-contact cases: zero inter-fibre contact edges;
- contact-rich cases: exactly the two predeclared disjoint contact edges and no others;
- path-match RMS <= 0.05 fibre diameter for every fibre;
- penetration <= 0.02 fibre radius;
- exact stable hold and inherited Stage28a numerical-health gates;
- immutable inputs, runner, records, histories, checkpoints, and hashes.

## Fail-closed order

1. Generate candidate geometries.
2. Independently audit geometry and paired matching.
3. Build a runner from the accepted Stage28a revision-2 contact-suppression implementation.
4. Independently audit the runner and release manifest.
5. Only a subsequent handoff may execute YADE.

## Authority

This contract authorizes design generation and independent design audit only. It does not authorize geometry acceptance, runner construction, YADE execution, GPU flow, permeability claims, mobile sand, deformation, clogging, migration, or coupling.
