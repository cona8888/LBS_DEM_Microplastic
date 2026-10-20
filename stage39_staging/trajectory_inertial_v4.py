"""Call-scoped binding of trajectory v1 to the warm multicontact solver."""
import trajectory_inertial_v1 as previous
import inertial_contact_v4 as inertial

lubrication = previous.lubrication
mechanics = previous.mechanics


def integrate(*args, **kwargs):
    prior = previous.inertial
    previous.inertial = inertial
    try:
        return previous.integrate(*args, **kwargs)
    finally:
        previous.inertial = prior
