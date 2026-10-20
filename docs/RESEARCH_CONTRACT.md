# Research Contract: Sand-Microplastic Permeability

This file records the decisions required before the full MatDEM specimen is
implemented. Unknowns remain explicit rather than being hidden in code
defaults.

## Primary question

Quantify how fixed and mobile microplastics change saturated sand permeability
under constant-head and falling-head tests. The quantitative claim remains
pending calibration and independent validation.

## Test definition

- Permeability regime: **saturated**
- Apparatus: **both constant-head and falling-head**
- Specimen geometry: **50 mm diameter, 20 mm height cylinder**
- Current reduced-model flow direction: vertical
- Constant-head gradient: **1.0 placeholder**
- Falling-head standpipe: **10 mm diameter placeholder**
- Falling-head interval: **100 mm to 20 mm placeholder**
- Water density and viscosity: nominal approximately 20 C values pending the
  measured laboratory temperature and chemistry
- Microplastic mobility: **both fixed and mobile populations are in scope**

The fidelity ladder treats these as two deliberately separated regimes:

1. **Fixed inclusions:** microplastics remain part of the granular skeleton and
   affect packing, pore geometry, throat size, tortuosity and permeability.
2. **Mobile particles:** a designated mobile fraction can detach or enter the
   flow, migrate between pores, become retained at throats and produce
   time-dependent clogging. Release and retention laws must be verified
   independently before interpreting column-scale permeability loss.

## Sand

- Active material: **Leighton Buzzard sand, Fraction B**
- Literature grading inputs: **D10 = 0.65 mm, D50 = 0.82 mm, Cu = 1.38**
- Literature density limits: **emin = 0.46, emax = 0.79**
- Active scenario: **Dr = 50%, e = 0.625, porosity = 0.3846**
- Source: *Effect of Sample Reconstitution Methods on the Behaviors of
  Granular Materials under Shearing*; source URL is recorded in the config
- Mineralogy and particle density - **unanswered**
- Particle shape/roundness representation - **unanswered**
- Specimen preparation and stress state - **unanswered**

The relative density is a selected scenario, not a measured input for the
user's specimen. The reduced model represents the grading by D50 spheres and
does not yet reproduce the full particle-size distribution or grain shape.

## Microplastics

- Polymer type - **unanswered**
- Shape: **generic sphere placeholder**
- Size: **0.30 D50 = 0.246 mm placeholder**; distribution unanswered
- Density and elastic properties - **unanswered**
- Sand-plastic and plastic-plastic friction - **unanswered**
- Active comparison: **clean plus 1% plastic solid volume**; the 1% level is a
  placeholder, not a literature-calibrated concentration
- Initial split between fixed and mobile populations - **unanswered**
- Detachment or release criterion for the mobile population - **unanswered**
- Pore-throat retention, remobilization and clogging rules - **unanswered**
- Spatial mixing method and possible segregation - **unanswered**

## Observables and validation

- Primary outputs: intrinsic permeability and hydraulic conductivity
- Constant-head observables: imposed head, steady discharge and recovered
  conductivity
- Falling-head observables: head-time curve, elapsed time and recovered
  conductivity
- Experimental clean-sand baseline - **unanswered**
- Experimental mixture data and replicate variability - **unanswered**
- Effluent microplastic concentration or retained-mass profile - **unanswered**
- Required pore-scale outputs - **unanswered**
- Acceptance tolerances - **unanswered**

## Planned evidence ladder

1. Native MATLAB-side MatDEM diagnostic attempted: protected `balance` did not
   advance time; no pass claimed. Standalone MatDEM remains the native target.
2. Transparent reduced two-pore solver verified against storage balance and
   analytical pressure decay: **passed**. This is not a `pore3d` result.
3. Reduced fixed/mobile microplastic mechanisms verified against the clean
   Kozeny-Carman limit and retained-mass balance: **passed as a toy model**.
4. Verify both hydraulic protocols against Darcy and analytical falling-head
   equations and demonstrate time-step convergence.
5. Native 3D MatDEM `pore3d` hydromechanical scripts prepared for the 50 mm by
   20 mm Leighton Buzzard Fraction B specimen; native execution pending.
6. Reproduce the MatDEM clean-specimen permeability workflow at reduced size,
   then execute the prepared application-scale specimen.
7. Verify head/flow proportionality and mass balance.
8. Demonstrate time-step, pore-network, seed and specimen-size convergence.
9. Calibrate clean-sand packing and hydraulic throat parameters.
10. Introduce one controlled fixed-inclusion representation in MatDEM.
11. Add and independently verify mobile release, transport and retention.
12. Calibrate only with designated mixture data.
13. Validate against held-out contents, sizes or hydraulic gradients.
14. Run a replicated parametric study with particle-generation seed separated
    from physical factors.
