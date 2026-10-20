# Stage36AD — independent periodic-sphere drag benchmark design

## Claim and comparator

The proposed benchmark asks whether the current immersed-boundary/LBM reference predicts the nonzero steady drag on one fixed sphere in creeping flow through a simple-cubic periodic array.

For sphere radius `a`, cubic period `L`, viscosity `mu` and superficial relative velocity `U`, define `lambda=a/L`. The dilute periodic mobility expansion is

`M(L)/M(infinity) = 1 - 2.837297 lambda + 4.19 lambda^3 - 27.4 lambda^7`,

and the corresponding drag comparator is

`F_H = 6*pi*mu*a*U / [M(L)/M(infinity)]`.

This is an external analytical comparator, not a force inferred from the numerical momentum ledger. Primary provenance: Hasimoto (1959), DOI `10.1017/S0022112059000222`; extended periodic-array calculations: Sangani and Acrivos (1982), DOI `10.1016/0301-9322(82)90047-7`.

## Frozen physical problem

- Three-dimensional incompressible creeping flow, one fixed no-slip sphere per periodic cubic cell.
- Fluid density 1 and kinematic/dynamic viscosity 0.1 in reference units.
- `lambda=0.125`; target Reynolds number `Re_p=2*a*U/nu <= 0.05`.
- Flow driven by a spatially uniform mean pressure gradient/body force with zero imposed particle motion.
- Measure the late-time mean fluid velocity relative to the sphere and the surface-exchange force on the sphere.
- Report `F_num/F_H`, transverse force, torque, mass drift, momentum ledger, density variation, marker slip and stationarity.

## Numerical ladder and gates

Analytical/resolution feasibility precedes flow execution. Candidate grids are `N=32,48,64`, giving 4, 6 and 8 lattice nodes per radius. `N=32` is a coarse diagnostic; only `N=48,64` may support the force conclusion.

Before any flow run, require:

- positive periodic mobility factor;
- `Re_p <= 0.05` and Mach number `U_lu/c_s <= 0.03`;
- at least four nodes per radius and a marker-spacing audit;
- a frozen steady-state rule based on both velocity and force over at least five viscous time windows;
- a documented forcing operator and half-step velocity convention;
- exact global momentum balance including the imposed body force and particle exchange.

Provisional force acceptance is not set in this design stage because truncation/model uncertainty of the analytical expansion at `lambda=0.125` must first be bounded against a higher-order/table value. No tolerance may be chosen from achieved numerical error.

## Claim boundary

Passing this benchmark would qualify steady, low-Re, spherical hydrodynamic drag only within its resolved radius and confinement range. It would not validate fibre torque, flexible-fibre dynamics, contacts, release fraction, permeability, or a soil-flushing campaign.
