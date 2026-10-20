"""Explicit per-trajectory Stage53 default and analytic contact recovery."""
import contact_dimensionless_lm_v1 as contact
import inertial_explicit_v1
import trajectory_explicit_v1

enrich = trajectory_explicit_v1.enrich
lubrication_matrix = trajectory_explicit_v1.lubrication_matrix


def integrate(*args, **kwargs):
    model = inertial_explicit_v1.ContactModel(
        contact._solve_prepared, contact.solve_recovery_prepared)
    before = contact.stats()
    result = trajectory_explicit_v1.integrate(*args, **kwargs, contact_model=model)
    after = contact.stats()
    result['contact_algorithm_stats'] = {k:after[k]-before[k] for k in after}
    return result
