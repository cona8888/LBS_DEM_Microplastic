"""Trajectory v2 with warm-started within-step multicontact iteration."""
import trajectory_inertial_v1 as previous
import inertial_contact_v4 as inertial

previous.inertial = inertial
integrate = previous.integrate
lubrication = previous.lubrication
mechanics = previous.mechanics
