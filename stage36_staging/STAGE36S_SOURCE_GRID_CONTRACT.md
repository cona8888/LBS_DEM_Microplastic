# Stage36S source-grid audit

No new flow solves. Keep Stage36Q field, sphereR=.2, outerL=.4,mu=.1,amplitude.01 unchanged. Evaluate steady source adv(u)-nu*lap(u) at cell centres for N16,24,32,48,64. Three fixed centre offsets in cell units:(0,0,0),(.13,.091,.039),(.37,.259,.111). Grid translations are numerical phase tests, not different physics.

Compute source integral dx^3*sum(b) against analytical Fx=.0016755160819145562. Compute source leaking into interior via trilinear interpolation and spherical quadrature, with(8,16,32) and(16,32,64) nodes. Exact continuum interior source is zero. Normalize all vector errors by nonzero analytical force. Report signed vectors, error and phase range; do not infer flow accuracy from source integration alone. Screening thresholds: source error<=2%, fine interior leakage<=2%, quadrature difference<=.2% of force. These are necessary diagnostic screens, not sufficient flow acceptance. No monotonicity assumed.

Reproduce Stage36R centred N16 steady interior correction against saved late-time history to1e-9 relative, using original(4,8,16) quadrature separately. Constant and linear trilinear reproduction tests tolerance1e-12. Parent/source hashes verified. Preserve all evidence. Do not launch larger flow jobs based solely on this audit.
