# Stage36AF — periodic-sphere benchmark runner implementation contract

## Scope

Implement and statically qualify a CPU reference runner for the Stage36AE fixed-sphere, simple-cubic benchmark. This stage may initialize geometry, operators and equilibrium state, but it must not advance a driven flow or create a numerical drag result.

## Frozen conventions

- D3Q19 BGK, `rho0=1`, `tau=0.8`, `nu=(tau-0.5)/3=0.1`.
- Triply periodic `N^3` cell; sphere at `(N/2,N/2,N/2)`, radius `N/8`.
- Four-point regularized-delta interpolation/spreading and fixed no-slip markers.
- Uniform body impulse is applied by an equilibrium-difference operator.
- Reported velocity `U` is total momentum divided by the whole periodic-cell volume (superficial/volume-average velocity).
- Force on the physical sphere is the negative marker impulse plus the change of fictitious interior-fluid momentum, minus the imposed source impulse deposited inside the fictitious sphere.
- The exact step ledger is `P_after-P_before-source_impulse-marker_impulse=0`.

## Frozen run ladder (not executed here)

- N32 diagnostic, followed only if healthy by N48 and N64 confirmations.
- Target `Re_p=0.05`; nominal target velocity is `Re_p*nu/(2a)`.
- Nominal source impulse per cell is selected from the Stage36AE reference drag divided by `N^3`; it is fixed, not feedback-controlled.
- Five full viscous windows after startup are required. A window is `N^2/nu` steps.
- Steady state requires, over each of the final five windows, both relative mean-velocity drift and relative mean-force drift `<=0.002`, with no monotonicity assumption.
- Force and resolution gates are inherited unchanged from Stage36AE: 3% and 2%.

This implementation stage does not authorize a driven run.
