# Native MatDEM 3D hydromechanical model

## Research question and claim boundary

The model asks how fixed spherical microplastic inclusions modify saturated
flow and particle rearrangement in a 50 mm diameter by 20 mm high Leighton
Buzzard Fraction B sand specimen. It is a two-way coupled pore-network/DEM
implementation: pore pressure generates particle forces, particle motion
changes pore geometry, and flow is recalculated.

The code is prepared from the installed MatDEM 5.00 `pore3d` examples. All 14
project configuration, volume, boundary, static-wiring and parser tests pass in
MATLAB R2024b. It has not
yet completed a native `pore3d` calculation, because `pore3d` is not exposed to
the shared MATLAB installation. Native execution must use the standalone
MatDEM application. No calibrated or validated permeability claim is made.

## Resolved specimen

- Cylinder: diameter 0.050 m, height 0.020 m
- Saturated vertical flow: top to bottom
- Hydraulic gradient: 1.0
- Head difference: 0.020 m
- Pressure difference: 196.133 Pa for water at 1000 kg/m3
- Sand: Leighton Buzzard Fraction B, represented by spheres
- Grading bounds: 0.60 to 1.18 mm
- Grading anchors: D10 = 0.65 mm, D50 = 0.82 mm, D60 = 0.897 mm
- Density state: Dr = 50%, e = 0.625, target porosity = 0.384615
- Microplastic: fixed spherical inclusions, diameter 0.246 mm
- Microplastic content: 1% of total solid volume
- Resolved count: approximately 64,800 sand particles plus 31,000
  microplastic particles, or about 95,800 particles total

The grading between reported points is a piecewise-linear inverse-CDF
reconstruction. It is an explicit model assumption, not a measured full sieve
curve. The relative density and microplastic content are selected scenarios.

## Numerical specimen preparation

The preparation stage places sand and microplastic centres randomly inside the
cylinder at 20% of their target radii. It then expands radii through nine
increments while particle friction is zero and balances the DEM assembly after
each increment. Target radii are not rescaled: particle counts are selected so
the summed solid volume matches the target porosity and 1% plastic solid-volume
fraction. Rough particle walls form the tube and the top and bottom discs.

This radius-expansion procedure should later be compared with an air-pluviation
or gravity-deposition preparation because preparation changes fabric,
coordination and permeability even at the same void ratio.

## Pore network and hydraulic boundaries

Stage 2 follows the installed MatDEM 3D permeability pattern:

```matlab
p = pore3d(d);
p.setInitialPores();
p.fKFlow(:) = config.fluid.throat_flow_factor;
p.setTimeStep();
```

Pores adjacent to the top and bottom boundary facets are obtained through
`p.GROUP.topF`, `p.GROUP.botF` and `p.facetP`. The top pressure is fixed at
reference pressure plus 196.133 Pa; the bottom remains at reference pressure.

The current throat-flow factor is `1e-8`, copied as an order-of-magnitude
placeholder from the installed MatDEM `pore3d` example. It must be calibrated
against clean Leighton Buzzard permeability before mixture predictions are
interpreted.

## Two-way coupling sequence

The coupling loop follows the installed `user_Pore3dCoupleTest3.m` sequence:

```matlab
p.balance(2);
p.fluid2Ball();
p.d.balance();
```

Boundary pressures are restored before every increment. The run records inlet
and outlet water mass per fluid step, relative mass-balance error, hydraulic
conductivity, mean pore pressure and maximum particle displacement. A run only
passes when pressure and particle coordinates remain finite, conductivity is
positive, and the maximum mass-balance error over the final five reporting
cycles is at most 2%.

The model uses fixed plastic particles. It does not yet implement detachment,
advection, throat capture or remobilization of mobile microplastics.

## Execution

In the standalone MatDEM command/editor environment:

```matlab
cd('C:\MATDEM_MICROPLASTIC')
run('scripts\run_native_matdem_hydromechanical_case.m')
```

The runner now performs native-runtime preflight checks before generating the
95,803-particle specimen. It stops immediately unless both `pore3d` and GPU
support are visible. MatDEM's `fs.randSeed` uses a small integer seed; this case
uses seed 1, matching the convention in the installed examples.

Or execute one stage at a time:

```matlab
projectRoot = "C:\MATDEM_MICROPLASTIC";
native_matdem_prepare_specimen(projectRoot)
native_matdem_initialize_pore3d(projectRoot)
native_matdem_run_coupled_permeability(projectRoot)
```

Results are written to:

```text
C:\MATDEM_MICROPLASTIC\runs\native_hm_lbsb_dr50_fixed_mp1
```

Stage 1 saves the equilibrated mixed specimen and its manifest. Stage 2 saves
the saturated `pore3d` network and boundary definition. Stage 3 writes cycle
checkpoints, a CSV history, a MAT result and a JSON pass/fail summary.

## Required verification before physical interpretation

1. Run a small clean fixed-bed pressure-gradient benchmark and close fluid
   mass balance.
2. Repeat using at least three fluid time-step scales.
3. Repeat using at least three fluid/mechanical coupling frequencies.
4. Compare clean-sand conductivity with measured Leighton Buzzard results and
   calibrate only the throat-flow factor.
5. Check particle overlap, force equilibrium, wall leakage and pressure-force
   direction.
6. Repeat the clean and 1% cases with at least three packing seeds.
7. Check particle-size/domain-size and wall-resolution sensitivity.
8. Freeze clean-sand parameters before evaluating microplastic effects.

The supplied sand and plastic material vectors are softened DEM placeholders.
They are numerical inputs, not measured grain Young's moduli or independently
calibrated sand-plastic contact properties.
