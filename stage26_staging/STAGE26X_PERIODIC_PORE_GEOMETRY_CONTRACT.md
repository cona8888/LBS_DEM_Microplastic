# Stage26x periodic LBS pore-geometry contract

Stage26x uses the accepted, already exported Stage25 216-grain periodic LBS
state at `e = 0.73858` and 100 Pa. It performs deterministic geometry analysis
only. Particle positions are wrapped into the central cell and replicated over
the nearest 27 periodic images for Delaunay-face throat and straight fibre-path
searches.

This route is selected because the Stage26w six-wall specimen hit its overlap
guard before exact radii were restored. The periodic cell removes the severe
wall-layer bias while retaining the user-selected 216 grains and the validated
LBS density state.

The search authorizes no DEM stepping, fibre mechanics, mobile sand, flow,
permeability, deformation, or production parametric claim. A separately frozen
design is required before any fixed-sand fibre execution.
