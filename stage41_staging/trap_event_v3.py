"""Finite contact-dwell diagnostic; this is not an absorbing retention law.

The input position is the interval endpoint and the generalized velocity is
constant over that accepted interval, with rotational entries ell*omega.
Translation plus integrated ell*|omega| bounds the motion of a prolate surface
point when ell is its major semiaxis. This deliberately includes axial spin.
"""
import numpy as np


class TrapMonitor:
    def __init__(self, reference_speed, minor_radius, dwell_time,
                 speed_ratio=0.01, drift_over_minor_radius=0.02,
                 minimum_load_bearing_contacts=1):
        values = (reference_speed, minor_radius, dwell_time, speed_ratio,
                  drift_over_minor_radius)
        if not np.isfinite(values).all() or min(values) <= 0:
            raise ValueError("finite positive trapping scales required")
        if (int(minimum_load_bearing_contacts) != minimum_load_bearing_contacts
                or minimum_load_bearing_contacts < 1):
            raise ValueError("positive integer contact count required")
        self.reference_speed = float(reference_speed)
        self.dwell_time = float(dwell_time)
        self.speed_ratio = float(speed_ratio)
        self.drift_limit = float(drift_over_minor_radius * minor_radius)
        self.minimum_contacts = int(minimum_load_bearing_contacts)
        self.reset()

    def reset(self):
        self.elapsed = 0.0
        self.anchor = None
        self.contact_ids = ()
        self.load_bearing_ids = ()
        self.angular_travel = 0.0
        self.maximum_drift = 0.0
        self.maximum_speed_ratio = 0.0

    def update(self, dt, position, generalized_velocity, contact_ids,
               load_bearing_contact_ids):
        x = np.asarray(position, float)
        velocity = np.asarray(generalized_velocity, float)
        if (not np.isfinite(dt) or dt <= 0 or x.shape != (3,)
                or velocity.shape != (6,) or not np.isfinite(x).all()
                or not np.isfinite(velocity).all()):
            raise ValueError("finite endpoint, velocity and positive dt required")
        contacts = tuple(sorted(set(int(k) for k in contact_ids)))
        bearing = tuple(sorted(set(int(k) for k in load_bearing_contact_ids)))
        linear_speed = float(np.linalg.norm(velocity[:3]))
        angular_speed = float(np.linalg.norm(velocity[3:]))
        ratio = max(linear_speed, angular_speed) / self.reference_speed
        eligible = (ratio <= self.speed_ratio and len(bearing) >= self.minimum_contacts
                    and set(bearing).issubset(contacts))
        if not eligible:
            self.reset()
            return self.state(False, ratio, 0.0)
        if (self.anchor is None or contacts != self.contact_ids
                or bearing != self.load_bearing_ids):
            self.reset()
            self.anchor = x - dt * velocity[:3]
            self.contact_ids = contacts
            self.load_bearing_ids = bearing
        self.angular_travel += dt * angular_speed
        excursion = float(np.linalg.norm(x - self.anchor)) + self.angular_travel
        if excursion > self.drift_limit:
            self.reset()
            return self.state(False, ratio, excursion)
        self.elapsed += dt
        self.maximum_drift = max(self.maximum_drift, excursion)
        self.maximum_speed_ratio = max(self.maximum_speed_ratio, ratio)
        return self.state(self.elapsed >= self.dwell_time, ratio, excursion)

    def state(self, observed, ratio, excursion):
        return {
            # Legacy key means only the declared finite dwell was observed.
            "trapped": bool(observed),
            "persistent_contact_observed": bool(observed),
            "elapsed_s": float(self.elapsed), "dwell_time_s": self.dwell_time,
            "instantaneous_speed_ratio": float(ratio),
            "maximum_speed_ratio": float(self.maximum_speed_ratio),
            "instantaneous_drift_m": float(excursion),
            "maximum_drift_m": float(self.maximum_drift),
            "angular_surface_travel_m": float(self.angular_travel),
            "contact_ids": list(self.contact_ids),
            "load_bearing_contact_ids": list(self.load_bearing_ids),
            "interpretation": "finite contact dwell, not irreversible retention",
        }
