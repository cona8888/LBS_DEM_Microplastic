# Stage28a Revision 2 — isolated path controls

The immutable Stage28a Design v1 and Candidate Geometry 01 are retained.  The
candidate search selected three open paths that do not have accepted isolated
mechanics histories: face indices 14848, 30311 and 30924.  Pairing them before
running them alone would confound path-specific sand response with
fibre-fibre interaction.

Revision 2 therefore adds three prerequisite isolated flexible-fibre controls,
one for each new path, using the identical fixed 216-grain sand state,
37-node fibre, pull history, contact model and numerical controls.  The
accepted Stage26x isolated histories remain the controls for face 37641
(open) and face 37527 (constricted).

The three paired cases remain unchanged.  In the two separated cases, each
terminal fibre centreline must agree with its path-matched isolated control
within 0.05 fibre diameters after minimum-image centroid alignment.  For the
crossing case, the interaction observable is the difference between the paired
terminal geometry and each of its two new isolated controls; no zero-deviation
gate is imposed.

This revision increases the mechanics batch from three to six executed cases:
three isolated controls followed by three paired cases.  It changes no
physical parameter, paired placement, loading path, hydraulic observable or
authority boundary.  It authorizes implementation and audit only; mechanics
execution remains false until an independent implementation release.

