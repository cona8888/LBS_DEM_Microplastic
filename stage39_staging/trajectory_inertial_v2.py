"""Trajectory v1 mechanics with the well-conditioned v3 closure audit."""
import trajectory_inertial_v1 as previous
import inertial_contact_v3 as inertial

# integrate resolves its module globals at call time; bind the corrected,
# mechanically equivalent step without duplicating the trajectory algorithm.
previous.inertial = inertial
integrate = previous.integrate
lubrication = previous.lubrication
mechanics = previous.mechanics
