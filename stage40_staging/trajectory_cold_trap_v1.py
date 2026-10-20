"""Call-scoped binding of the trapping state machine to cold Coulomb solves."""
import trajectory_cached_trap_v1 as previous
import inertial_contact_cold_v1 as inertial

trap_event_v2 = previous.trap_event_v2


def integrate(*args, **kwargs):
    prior = previous.inertial
    previous.inertial = inertial
    try:
        return previous.integrate(*args, **kwargs)
    finally:
        previous.inertial = prior
