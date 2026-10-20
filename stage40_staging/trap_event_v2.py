"""Persistent-contact trapping event with interval-consistent dwell accounting."""
import numpy as np
import trap_event_v1 as previous


class TrapMonitor(previous.TrapMonitor):
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
        if not eligible:
            self.reset()
            return self.state(False, speed_ratio, 0.0)
        if contacts != self.contact_ids or self.anchor is None:
            self.reset()
            self.anchor = position.copy()
            self.contact_ids = contacts
            self.elapsed = dt
            self.maximum_speed_ratio = speed_ratio
            return self.state(self.elapsed >= self.dwell_time, speed_ratio, 0.0)
        drift = float(np.linalg.norm(position - self.anchor))
        if drift > self.drift_limit:
            self.reset()
            return self.state(False, speed_ratio, drift)
        self.elapsed += dt
        self.maximum_drift = max(self.maximum_drift, drift)
        self.maximum_speed_ratio = max(self.maximum_speed_ratio, speed_ratio)
        return self.state(self.elapsed >= self.dwell_time, speed_ratio, drift)
