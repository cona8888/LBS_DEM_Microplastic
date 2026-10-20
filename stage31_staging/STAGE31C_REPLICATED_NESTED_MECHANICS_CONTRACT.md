# Stage31c replicated nested-fibre mechanics contract

## Question

Do the six audited packing-by-placement blocks remain mechanically valid under the already qualified F37 fixed-sand pull protocol, so their terminal centreline prefixes can support a later replicated 1/2/4-fibre hydraulic campaign?

## Minimal execution

- Run one four-fibre mechanics case for each of three independently prepared sand packings and two placement blocks: six YADE cases total.
- Keep all sand particles and the periodic cell exactly fixed.
- Use the unchanged Stage29d F37 material, contact, loading, damping, and time-step controls.
- Give each fibre an isolated collision group while retaining sand contact.
- Record all four terminal centrelines. Later 1-, 2-, and 4-fibre hydraulic geometries may use only the corresponding nested prefixes from the same four-fibre realization.

This six-case construction is preferable to 18 redundant mechanics runs because fixed sand and the required absence of any fibre-fibre interaction make the four terminal paths mechanically separable. The runner must nevertheless prove that no cross-fibre contact or node bond occurs at any sampled time.

## Hard gates

- 216 sand particles, 37 nodes and 36 internal bonds per fibre.
- Exact fixed-sand and fixed-cell closure.
- Zero-load hold drift and speed within the accepted Stage29d limits.
- Penetration no greater than the accepted Stage29d limit.
- No fibre-fibre contacts, cross-fibre node interactions, or intrafibre grid contacts at any time.
- Finite histories and four terminal centrelines for every block.
- Frozen config, runner, design, audit, render, checkpoint, and prior-mechanics hashes must match.

## Authority boundary

The preflight remains fail-closed. Only a separate independent release may authorize these six CPU YADE mechanics cases. Successful mechanics does not authorize LBM/GPU flow, a permeability claim, mobile sand, migration, clogging, deformation, or coupling.
