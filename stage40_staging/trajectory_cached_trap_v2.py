"""Call-scoped normal-only cache binding for the verified trajectory state machine."""
import trajectory_cached_trap_v1 as previous
import inertial_contact_cached_v2 as inertial

trap_event_v2 = previous.trap_event_v2


def integrate(*args, **kwargs):
    prior = previous.inertial
    previous.inertial = inertial
    try:
        return previous.integrate(*args, **kwargs)
    finally:
        previous.inertial = prior
