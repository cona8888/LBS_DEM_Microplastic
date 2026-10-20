# Stage26q friction-reduction preparation addendum

## Trigger

The sign-corrected clean density-controller pilot compressed quasi-statically
from `e = 1.02393` to `e = 0.86053`, then stopped at the declared 5% overlap
hard guard. At that stop the unbalanced force was `1.08e-4` and kinetic energy
divided by `pV` was `3.56e-6`; therefore the limitation is a frictionally locked
contact network, not excessive loading rate.

## Single bounded correction

Use sand–sand friction coefficient `mu_prep = 0.30` only during the isotropic
density ramp. On first reaching `e = 0.744`, stop the walls and restore
`mu_sand = 0.60` in both the material and every existing sand–sand interaction.
Then run the unchanged fixed-volume equilibrium and 100 Pa stress-restoration
gates.

The value 0.30 is already inside the Stage25 preparation screen. It is a
specimen-generation control, not a calibrated material property. Wall friction
remains zero. Particle radii, density, contact stiffness, damping, target state,
overlap guards and final acceptance gates remain unchanged.

## Falsification rule

If the 5% overlap hard guard is reached again before `e = 0.744`, or if the
restored-friction state cannot retain `e = 0.744 +/- 0.02` at 100 Pa, preserve
the failure and do not try lower preparation friction automatically. The next
decision must then address boundary/initialization model form explicitly.

## Authority

This addendum authorizes one clean-sand `mu_prep = 0.30` attempt. It does not
authorize a second friction level, fibre insertion, flexible fibres, flow,
permeability, deformation, migration, or a production parametric study.

