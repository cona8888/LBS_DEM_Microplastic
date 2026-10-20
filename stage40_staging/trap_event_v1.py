"""Conservative persistent-contact trapping event for steady frozen flow."""
import numpy as np


class TrapMonitor:
    def __init__(self, reference_speed, minor_radius, dwell_time,
                 speed_ratio=0.01, drift_over_minor_radius=0.02,
                 minimum_load_bearing_contacts=1):
        if min(reference_speed, minor_radius, dwell_time) <= 0:
            raise ValueError("positive scales required")
        if speed_ratio <= 0 or drift_over_minor_radius <= 0:
            raise ValueError("positive trapping thresholds required")
        if minimum_load_bearing_contacts < 1:
            raise ValueError("at least one load-bearing contact required")
        self.reference_speed = float(reference_speed)
        self.minor_radius = float(minor_radius)
        self.dwell_time = float(dwell_time)
        self.speed_ratio = float(speed_ratio)
        self.drift_limit = float(drift_over_minor_radius) * self.minor_radius
        self.minimum_contacts = int(minimum_load_bearing_contacts)
        self.reset()

    def reset(self):
        self.elapsed = 0.0
        self.anchor = None
        self.contact_ids = None
        self.maximum_drift = 0.0
        self.maximum_speed_ratio = 0.0

    def update(self, dt, position, generalized_velocity, contact_ids,
               load_bearing_contact_ids):
        if dt <= 0:
            raise ValueError("positive dt required")
        position = np.asarray(position, float)
        velocity = np.asarray(generalized_velocity, float)
        if position.shape != (3,) or velocity.shape != (6,):
            raise ValueError("invalid state")
        contacts = tuple(sorted(int(value) for value in contact_ids))
        load_bearing = tuple(sorted(int(value) for value in load_bearing_contact_ids))
        speed = max(np.linalg.norm(velocity[:3]), np.linalg.norm(velocity[3:]))
        speed_ratio = float(speed / self.reference_speed)
        eligible = (speed_ratio <= self.speed_ratio
                    and len(load_bearing) >= self.minimum_contacts
                    and set(load_bearing).issubset(contacts))
        if not eligible or contacts != self.contact_ids:
            self.reset()
            if eligible:
                self.anchor = position.copy()
                self.contact_ids = contacts
            return self.state(False, speed_ratio, 0.0)
        if self.anchor is None:
            self.anchor = position.copy()
            self.contact_ids = contacts
        drift = float(np.linalg.norm(position - self.anchor))
        if drift > self.drift_limit:
            self.reset()
            return self.state(False, speed_ratio, drift)
        self.elapsed += dt
        self.maximum_drift = max(self.maximum_drift, drift)
        self.maximum_speed_ratio = max(self.maximum_speed_ratio, speed_ratio)
        trapped = self.elapsed >= self.dwell_time
        return self.state(trapped, speed_ratio, drift)

    def state(self, trapped, speed_ratio, drift):
        return {
            "trapped": bool(trapped),
            "elapsed_s": float(self.elapsed),
            "dwell_time_s": self.dwell_time,
            "instantaneous_speed_ratio": float(speed_ratio),
            "maximum_speed_ratio": float(self.maximum_speed_ratio),
            "instantaneous_drift_m": float(drift),
            "maximum_drift_m": float(self.maximum_drift),
            "contact_ids": [] if self.contact_ids is None else list(self.contact_ids),
        }
