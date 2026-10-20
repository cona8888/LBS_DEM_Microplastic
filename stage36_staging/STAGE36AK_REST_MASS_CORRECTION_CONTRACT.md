# Stage36AK — zero-momentum mass-restoration equivalence contract

After each otherwise unchanged Stage36AH step, compute the global mass residual
`delta = N^3 - sum(f)`. Add `delta` to the D3Q19 rest population (`q=0`) at
the deterministic periodic cell `(0,0,0)`. Since its discrete velocity is zero,
the correction adds exactly zero momentum. Reject nonfinite corrections or any
correction with magnitude above `1e-9` LU per step.

Compare corrected and uncorrected N32 paths from identical equilibrium states for
256 driven steps. Before seeing results, freeze these gates:

- maximum x-force difference / Stage36AE reference force `<=1e-8`;
- maximum x-velocity difference / target velocity `<=1e-8`;
- corrected cumulative mass drift `<=1e-14`;
- momentum-ledger residual `<=1e-11` LU;
- density error `<=0.01`, marker slip `<=1e-8`, all populations positive;
- maximum absolute per-step mass correction `<=1e-9` LU.

Passing qualifies only the correction operator and a fresh immutable N32 rerun.
It does not validate drag or authorize N48/N64.
