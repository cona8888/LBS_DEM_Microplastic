# Stage26r periodic radius-restoration contract

## Physical and numerical question

Can the accepted 216-sphere periodic Stage25 LBS state be temporarily opened by
shrinking the sand radii and then recover its exact grading, target void ratio,
100 Pa stress and load-bearing network after controlled radius restoration?

This clean benchmark is required before placing any fibre into the opened
periodic state. It addresses the wall-locking failure observed in Stage26q; it
does not itself represent physical pluviation.

## Frozen system

- source: accepted Stage25 `mu_0.60` periodic checkpoint;
- 216 spherical LBS grains, exact original positions, radii, density and cell;
- initial and final sand friction coefficient 0.60;
- temporary preparation friction coefficient 0.30;
- zero gravity and fixed periodic cell;
- shrink factor 0.80, followed by 200 equal logarithmic radius increments;
- particle mass and inertia updated with every radius change;
- no fibre and no fluid.

## Observables and gates

- exact recovery of every original radius to relative error `<= 1e-12`;
- exact particle count and unchanged periodic cell;
- final void-ratio difference from the accepted Stage25 value `<= 0.002`;
- mean compression-positive stress error from 100 Pa `<= 5%`;
- maximum principal stress error `<= 10%`;
- unbalanced force `<= 0.03`;
- kinetic energy divided by `pV <= 1e-5`;
- maximum overlap divided by smaller radius `<= 0.02`, hard stop at 0.05;
- coordination excluding iterative degree-less-than-two rattlers `>= 3.0`;
- rattler fraction `<= 0.35`;
- five consecutive passing hold blocks.

## Interpretation

Pass: the opened periodic-state preparation algorithm is numerically qualified
for a later single-fibre insertion design. It does not prove that the fibre will
be trapped.

Fail: preserve the failure and do not insert a fibre. A different initialization
or larger-domain model is required.

## Authority

One clean radius-restoration run is authorized. No fibre, flexible-fibre,
flow, permeability, deformation, migration or production-parametric execution
is authorized.

