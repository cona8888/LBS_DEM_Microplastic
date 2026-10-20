# Stage36AH — constant-reference-density projection equivalence contract

The candidate acceleration replaces the per-step dense factorization of
`J diag(1/rho) J^T` with one Cholesky factorization of `J J^T` at `rho0=1`.
All collision, forcing, streaming, interpolation, force reconstruction and
momentum-ledger operations remain unchanged.

Before a full run, compare exact and accelerated N32 paths for 128 driven
startup steps from identical equilibrium states. The candidate passes only if:

- maximum relative x-force difference, scaled by the Stage36AE reference force, is `<=1e-4`;
- maximum x superficial-velocity difference, scaled by target velocity, is `<=1e-5`;
- accelerated marker slip is `<=1e-8` LU;
- accelerated mass drift is `<=1e-12`, density error `<=0.01`, and momentum residual `<=1e-11` LU;
- accelerated wall time is lower than exact wall time.

These gates are fixed before execution. Equivalence here is restricted to this
low-Mach N32 startup trajectory; it does not establish steady drag accuracy.
