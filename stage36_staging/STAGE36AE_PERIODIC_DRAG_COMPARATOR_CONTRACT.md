# Stage36AE — periodic-sphere drag comparator qualification

## Purpose

Qualify and freeze the external force comparator for the Stage36AD simple-cubic periodic-sphere benchmark before any flow result exists. This addendum preserves Stage36AD as immutable evidence and corrects its exponent transcription.

## Primary-source relation

Ladd (1994), *Journal of Fluid Mechanics* 271, 311–339, Eq. (3.5), DOI `10.1017/S0022112094001771`, gives the low-concentration simple-cubic drag relation

`6*pi*eta/xi_T = 1/a - 2.837/L + 4.19*a^2/L^3 - 27.4*a^5/L^6`.

Therefore, with `lambda=a/L`,

`M(lambda) = 6*pi*eta*a/xi_T = 1 - 2.837*lambda + 4.19*lambda^3 - 27.4*lambda^6`,

and `F_ref/(6*pi*mu*a*U) = 1/M(lambda)`.

Hasimoto (1959), DOI `10.1017/S0022112059000222`, is the analytical origin. Sangani and Acrivos (1982), DOI `10.1016/0301-9322(82)90047-7`, independently extended periodic-array calculations across the concentration range.

## Frozen reference and uncertainty

- Geometry: `lambda=0.125`, hence sphere fraction `phi=(4*pi/3)*lambda^3`.
- Nominal comparator: the Ladd Eq. (3.5) coefficient set above.
- Coefficient-rounding check: replace `2.837` by the more precise periodic constant `2.837297`; retain the published rounded higher-order coefficients.
- Reference uncertainty is conservatively frozen at **1.0% relative**, which exceeds the difference between those two evaluations and covers printed-coefficient rounding. This is a comparator-use allowance, not a statistical confidence interval.

## Predeclared numerical acceptance

Only `N=48` and `N=64` can support the force conclusion. Both must satisfy:

1. `abs(F_num/F_ref - 1) <= 0.03`;
2. `abs(F64/F48 - 1) <= 0.02`;
3. all Stage36AD Reynolds, Mach, steady-state, density, slip, transverse-force, torque, mass-drift and exact global momentum-balance gates.

The 3% comparison band is fixed as a 1% comparator allowance plus a 2% numerical target. Passing means the method resolves nonzero steady spherical drag for this geometry only. Failure is not retuned.

No flow may be launched until the qualification script passes and its hashes are recorded.
