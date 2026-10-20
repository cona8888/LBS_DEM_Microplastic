"""Experimental PGS-prefix acceleration; same equations, selection unqualified."""
import contact_pgs_prefix_optional as contact
import inertial_explicit_v1
import trajectory_explicit_v1


def integrate(*args, **kwargs):
    model = inertial_explicit_v1.ContactModel(contact.solve_prepared)
    before = contact.stats()
    result = trajectory_explicit_v1.integrate(*args, **kwargs, contact_model=model)
    after = contact.stats()
    result['contact_algorithm_stats'] = {k:after[k]-before[k] for k in after}
    result['algorithm_status'] = 'experimental_pgs_prefix_analytic_acceleration'
    return result
