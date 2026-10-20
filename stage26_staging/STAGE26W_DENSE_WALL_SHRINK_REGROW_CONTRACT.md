# Stage26w dense six-wall shrink-regrow preparation contract

## Question

Can the accepted Stage26o 216-grain, six-wall LBS specimen be re-prepared near
the reference void ratio without the premature frictional locking observed in
Stage26q?

## Bounded method

1. Load the immutable accepted Stage26o wall state.
2. Preserve the six-wall aspect ratio and resize the wall volume to the target
   container void ratio `e = 0.744`.
3. Affinely map particle centres into the resized cell and temporarily shrink
   particle radii to `0.78` of their final values.
4. Restore the exact radii gradually with zero sand-sand friction while the
   walls remain fixed, allowing rearrangement instead of overlap accumulation.
5. Hold at fixed volume, restore the LBS sand friction coefficient `mu = 0.60`,
   then use the existing six-wall stress servo to approach 100 Pa.
6. Save a state only if density, stress, force balance, kinetic energy, overlap,
   coordination, rattler, particle-count, and leakage gates all pass for five
   consecutive blocks.

The temporary zero-friction stage is a specimen-preparation device, not a
calibrated material property. Particle radii, grading, density, elastic contact
parameters, final friction, target stress, and final acceptance gates are not
changed.

## Falsification

The pilot fails closed if it exceeds 5% normalized penetration, loses a grain,
cannot restore exact radii, or cannot satisfy the final gates within the
predeclared resource ceiling. A failed pilot is evidence about the preparation
protocol and does not authorize automatic tolerance relaxation.

## Authority boundary

This contract authorizes one clean-sand Stage26w preparation pilot and an
independent evaluation. Pore-throat extraction is authorized only after an
accepted state. Fibre insertion, mobile-sand mechanics, flow, permeability,
deformation, and production parametric studies remain unauthorized by this
contract.
