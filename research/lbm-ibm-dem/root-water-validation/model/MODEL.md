# Model note | Does the location of water extraction change grain attraction?

## Question and test

Consider one rigid, porous root analogue (radius 1 mm), one movable grain (radius 0.35 mm) and an initially connected water bridge. The initial nominal surface gap is 0.60 mm. The grain is supported by a linear spring. We compare a root membrane with a sink at the outer side of a hydraulically connected reservoir. For the outer case we impose the *actual flux history measured in the simulated root case*, increment by increment. A sealed specimen is the third control. Identical removal and actuator motion do not impose identical water distribution, grain motion or meniscus shape. The model measures these differences rather than assuming a contact attraction.

This is a two-dimensional cross-section with unit out-of-plane depth. Water volume per unit depth is area (m²); force per unit depth is N/m. Only **normal opening of an existing connected meniscus** is admissible. This is neither axial root pull-out nor a soil-strength test.

## 1. Resolved near pore

On the moving finite-volume mesh we minimise the following dimensionless energy at fixed liquid-equivalent area. The liquid and gas correspond approximately to phase variable `φ=+1` and `φ=-1`.

```text
E = ∫Ω [ (φ²−1)²/4 + κ |∇φ|²/2 ] dA  − (σ*/4) ∫wall cos(θ) (3φ−φ³) ds
Aw = ∫Ω (1+φ)/2 dA          μ = (1/2) ∂Eeq/∂Aw
Fg = −P0 Δx0 (dEeq/dg*)|Aw       (negative is attraction towards the root)
```

Here `g*` is the gap in reference spacings `Δx0 = 50 µm`; `W=2.5`, `κ=W²/2`, `σ*=2W/3` and `P0=γ/(σ*Δx0)=864 Pa`, for `γ=0.072 N/m`. The stencil uses face length divided by centre distance, including nonuniform spacing. The wall potential uses **nominal** contact-angle inputs of 50° (root) and 60° (grain) measured through liquid; the effective angles on rasterised disks have not been calibrated. The wall quadrature on staircase masks and the fixed physical diffuse interface thickness are remaining sources of numerical bias. `Aw` is a conserved diffuse-phase inventory, *not* a measured volume or the thresholded area of the liquid region; φ need not be strictly within ±1.

A moving mesh translates the grain-side cells and stretches fluid strips only. This keeps the disk masks and exposed wall lengths fixed during normal motion. A projected L-BFGS solve re-equilibrates φ at exactly the supplied area. The maximum deviation of discrete chemical potential from equilibrium must be below `4e-6` reference pressure units. The shape derivative includes the constraint term `−μ ∂g∑ V(1+φ)`. An independently discretised Korteweg stress is integrated around four different closed fluid contours per solid. The contour force is **not** added to the energy-derived load. At the initial 50 µm state the grain contour gives −0.16257 N/m, the archived v0.1 contour −0.16265 N/m, and the energy derivative −0.16484 N/m. These operators agree in sign, not exactly in value; the discrepancy is retained, not corrected away.

At local equilibrium we infer soil-side water potential `ψn = pl−pg` from the two stable roots of `φ³−φ=μ`, using `p(φ)/P0=μφ−(φ²−1)²/4`. This is a **bulk-branch reconstruction**, not an independent dynamic pressure measurement. The resolved spatial quantity is the phase/stress field; the near pore has one equilibrium bulk pressure difference, while the outer compartment can differ. The pressure inside an unresolved root axis is prescribed; no osmotic or gravitational head is included. Absence of a connected positive-φ path between grain and root aborts the run. The cutoff does not model bridge rupture or refilling.

## 2. Water exchange and mechanical feedback

For root wet perimeter `Lw(φ)` and xylem pressure `ψx`, the one-way membrane and two-compartment exchange laws are:

```text
Qr = Lp Lw(φ) max(ψn−ψx, 0)                 positive to the root
Qℓ = G(ψo−ψn),      ψo = ψo0 + (Ao−Ao0)/C   positive from outer to near pore
dAn/dt = Qℓ−Qr,      dAo/dt = −Qℓ−Qout
d(An + Ao + Ar + Aout)/dt = 0
```

`Lw` is the integral of a smooth phase indicator on root-facing fluid faces. The membrane exchanges a *water inventory* with the near pore; mass is not removed at individual immersed-boundary markers during a fluid step. `G=10⁻¹³ m²/(Pa s)` and `C=2×10⁻⁹ m²/Pa` are a reduced hydraulic connection and storage, not a simulated outer grain packing. The membrane coefficient is `3×10⁻¹⁰ m/(Pa s)` and `ψx=−110 Pa`; the outer compartment initially contains `2×10⁻⁶ m²`. All are illustrative, not measured tree or soil parameters. The local and outer compartments initially have the same potential on each mesh. The fine run retains the same total starting water and support position, not an artificially matched mesh pressure.

After each hydraulic increment we find a consistent `(field, grain gap)`: at the current gap solve the phase field, send signed field load to the C++ v0.3 DEM, relax the spring-supported native mobile disk, update the mesh and repeat. Accept only when `|Fg+k(ga−g)|<10⁻⁷ N/m` and displacement change is below `10⁻¹⁰ m`. `k=2500 N/m²`. The fixed root carries the opposite applied load, while independent contour measurements check the sign and balance. The numerical damping of the native integrator is only a quasi-static relaxation; it does not specify water viscosity. There is no phenomenological adhesive force, fitted JKR term, or added suction-dependent friction. Contact is expressly disallowed in this benchmark.

## 3. Matched-history experiment and results

Condition for one simulated hour, 18 hydraulic increments at 200 s. Seal the membrane and outer exchange; open the spring support by 75 µm in 9 equilibrium increments. The ordering represents fast loading compared with inter-compartment supply but slow loading compared with equilibration *inside* the bridge. No physical pull rate or rupture work is inferred. There is no remote evaporation or air invasion simulation; outer drainage is a prescribed reservoir outflow.

| Complete run | Root uptake: attraction | Matched outer drainage: attraction | Sealed: attraction | Root vs outer |
|---|---:|---:|---:|---:|
| 50 µm, 200 s, 9 opening increments | 0.15399 N/m | 0.16079 N/m | 0.16103 N/m | −4.23% |
| 50 µm, 100 s, 18 opening increments | 0.15406 N/m | 0.16078 N/m | 0.16103 N/m | −4.18% |
| 25 µm, 200 s, 9 opening increments | 0.15728 N/m | 0.16303 N/m | 0.16317 N/m | −3.53% |

Each *pair* removes the same water at every increment. The quantity removed varies slightly *between* refinements because membrane flux is solved, not fitted (0.06543–0.06563 mm²). On the base grid after opening, root uptake leaves 0.25980 mm² in the near pore versus 0.31935 mm² under outer drainage. The wetted root lengths are 0.8583 vs 0.9881 mm. The resulting actual gaps differ (679.34 vs 676.62 µm). To separate water location from spring displacement, hold both grains at **677.5 µm actual gap** and independently re-equilibrate the fields at the end-of-path inventories. The root/outer attractions at fixed gap are 0.15447/0.16073 N/m at 50 µm and 0.15741/0.16294 N/m at 25 µm. Thus the direction survives this control: −3.90% and −3.39%, respectively. The independent contour calculation has the same ordering. Raw data: `results/identical_grain_gap.csv`.

![Same actuator opening; root uptake and outer-drainage zero-phase contours, base grid. Grey disks are from the root-uptake run.](figures/02_meniscus/figure.png)

The sign persists under the two refinements; two grids do not establish an asymptotic effect size. Before opening, the difference in attraction on the finer mesh is small; do not generalise the post-opening result to all gaps. In particular, the macroscopic pull-out *increase* reported by Kamchoom et al. involves root–soil shear and constrained dilatancy, which this open gap excludes. Treat both as potentially coexisting mechanisms.

## 4. Verification and falsification

The executable tests include finite-difference checks of energy, force and storage; a no-liquid zero-load/no-uptake limit; cross-contour balance; comparison with the archived v0.1 grain-force result; an independent spring equilibrium oracle; exact replay of extracted water; equivalence of all three methods when extraction is disabled; and rejection of invalid or dry-out states. All three complete runs close the diffuse-water ledger to less than `1.5×10⁻²¹ m²` and the force residual to less than `10⁻⁷ N/m`. These are algorithmic balances, not error bars or field validation. The unmodified parent native regression tests were also built and run.

**First physical test.** Use a transparent slit cell, porous cylindrical root analogue and a single wettable disk/long cylindrical grain on a compliant force probe. Measure the surface tension, both contact angles (advancing/receding), membrane flow–pressure curve, inter-reservoir conductance and probe stiffness independently. Track extracted water, actual gap, wetted root length and normal force at fixed bulk extraction and fixed actual gap for both drying paths. A metre-depth force is not applicable to a glass sphere: use a slit of known thickness with end effects quantified, or build the 3-D benchmark before using beads. Repeat after a long equilibration hold to probe the finite-supply mechanism. Failure to reproduce both footprint and force without changing fitted parameters across treatments is evidence against the model. Later, in a bead pack, measure pull-out force **and** local suction; that is a separate validation target.

**Next implementation.** Retain this test as a quasi-static reference. Implement conservative Allen–Cahn phase transport and a single consistent multiphase momentum scheme with a conservative permeable IBM boundary; independently check Laplace pressure, equilibrium contact angles, nonphysical currents and liquid inventory at a moving wall. Only then introduce contacts, rupture/reformation, multiple grains, root bending and axial pull-out. Reaching those milestones, not simply counting components, would justify a claim about tree anchorage.

## Evidence and design provenance

The source brief was *Development plan for a pore-scale root–soil LBM–IBM–DEM model* (project report, 2 November 2026). This release implements its field-load/no-double-counting and water-ledger principles, not its complete recommended production solver. Phase-field LBM–DEM itself and suction-controlled porous roots are **not** claimed as new. Relevant primary studies:

- Younes et al., [DEM–LBM coupling for partially saturated granular assemblies](https://www.sciencedirect.com/science/article/pii/S0266352X23004342): existing multiphase numerical comparator.
- Younes and colleagues, [Parameter optimization of phase-field-based LBM model for calculating capillary forces](https://doi.org/10.1016/j.compgeo.2024.106391): sensitivity of quantitative capillary-force predictions.
- Ng, Leung, Kamchoom & Garg, [A novel root system for simulating transpiration-induced soil suction in centrifuge](https://discovery.dundee.ac.uk/en/publications/a-novel-root-system-for-simulating-transpiration-induced-soil-suc/): basis for a controllable porous-root validation.
- Kamchoom, Leung & Ng, [Effects of root geometry and transpiration on pull-out resistance](https://doi.org/10.1680/geolett.14.00086): separate macroscopic pull-out target.
