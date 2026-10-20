# Stage27b CPD4 solution-verification contract

Stage27b repeats the exact Stage27a clean, open-path and contact-deflected
fixed-solid periodic geometries at twice the lattice resolution in every
direction (CPD4, 186 cubed). No physical parameter or geometry is retuned.

The primary verification quantities are the two paired permeability ratios and
the contact-deflected-minus-open contrast. Acceptance requires: all inherited
GPU health, steady-state and momentum-balance gates; both fibre effects remain
negative; the deflected case remains more obstructive than the open case; each
paired-ratio CPD2-to-CPD4 shift is at most 0.002; and the placement-contrast
shift is at most 0.001. These are numerical verification bounds, not
experimental tolerances.

CPD2 final fields provide declared resampled warm starts using the previously
verified Stage24 CPD2-to-CPD4 scaling (velocity 0.5, density deviation 0.125).
Raw CPD2 and CPD4 results remain separate and immutable.

The claim remains one fibre in one 216-grain periodic realization. Stage27b
does not authorize a physical concentration law, absolute-permeability
validation, mobile grains, clogging evolution, polymer-flow deformation, or
two-way coupling.

