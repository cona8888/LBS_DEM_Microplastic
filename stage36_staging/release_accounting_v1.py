"""Axial-capsule bookkeeping oracle; prescribed positions, no physics engine."""
from dataclasses import dataclass
from math import fsum, isfinite

TOL = 1e-12


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


@dataclass(frozen=True)
class Body:
    body_id: str
    mass_kg: float
    length_m: float
    radius_m: float

    def __post_init__(self):
        if not isinstance(self.body_id, str) or not self.body_id.strip():
            raise ValueError("body_id must be nonempty")
        for key in ("mass_kg", "length_m", "radius_m"):
            object.__setattr__(self, key, finite(getattr(self, key), key))
        if self.mass_kg <= 0 or self.length_m < 0 or self.radius_m <= 0:
            raise ValueError("invalid body dimensions or mass")
        if not isfinite(self.length_m / self.radius_m + 4 / 3):
            raise ValueError("aspect ratio outside finite range")


def fraction_left(body, relative_plane_m):
    """Exact volume CDF for x-aligned capsule, plane relative to its centre."""
    z = finite(relative_plane_m, "relative plane") / body.radius_m
    half = body.length_m / (2 * body.radius_m)
    total = 2 * half + 4 / 3
    if z <= -half - 1:
        return 0.0
    if z >= half + 1:
        return 1.0
    if z < -half:
        h = z + half + 1
        return h * h * (1 - h / 3) / total
    if z > half:
        h = half + 1 - z
        return 1 - h * h * (1 - h / 3) / total
    return (2 / 3 + z + half) / total


def partition(body, centre_m, inlet_m, outlet_m):
    x = finite(centre_m, "centre")
    a, b = finite(inlet_m, "inlet"), finite(outlet_m, "outlet")
    if a >= b:
        raise ValueError("inlet must precede outlet")
    up = fraction_left(body, a - x)
    # Symmetry evaluates a small downstream tail without subtracting near-one values.
    down = fraction_left(body, x - b)
    inside = fsum((1.0, -up, -down))
    if inside < -TOL or inside > 1 + TOL:
        raise ValueError("invalid geometric partition")
    return (up, max(0.0, min(1.0, inside)), down)


class Ledger:
    """All tagged IDs remain tracked. No body deletion, absorption or fracture."""
    def __init__(self, bodies, positions, inlet_m, outlet_m, pore_volume_m3):
        self.bodies = {}
        for body in bodies:
            if not isinstance(body, Body) or body.body_id in self.bodies:
                raise ValueError("invalid or duplicate body")
            self.bodies[body.body_id] = body
        if not self.bodies:
            raise ValueError("empty inventory")
        self.inlet = finite(inlet_m, "inlet")
        self.outlet = finite(outlet_m, "outlet")
        self.pore_volume = finite(pore_volume_m3, "pore volume")
        if self.inlet >= self.outlet or self.pore_volume <= 0:
            raise ValueError("invalid domain or pore volume")
        self.mass0 = fsum(b.mass_kg for b in self.bodies.values())
        if not isfinite(self.mass0):
            raise ValueError("nonfinite total mass")
        parts, _ = self._snapshot(positions)
        if any(p[0] != 0 or p[2] != 0 for p in parts.values()):
            raise ValueError("initial body is not wholly inside")
        self.parts = parts
        self.time = 0.0
        self.water_in = self.water_out = 0.0
        self.gross_out = self.gross_return = 0.0
        self.gross_up = self.gross_up_return = 0.0
        self.complete = set()
        self.ever_complete = set()
        self.complete_events = 0

    def _snapshot(self, positions):
        seen, parts, complete = set(), {}, set()
        for key, value in positions:
            if key in seen or key not in self.bodies:
                raise ValueError("duplicate or unknown position ID")
            seen.add(key)
            body = self.bodies[key]
            x = finite(value, "position")
            parts[key] = partition(body, x, self.inlet, self.outlet)
            if x - body.length_m / 2 - body.radius_m >= self.outlet:
                complete.add(key)
        if seen != set(self.bodies):
            raise ValueError("missing position ID; deletion is prohibited")
        return parts, complete

    def step(self, time_s, positions, inlet_water_m3=0.0, outlet_water_m3=0.0):
        t = finite(time_s, "time")
        wi = finite(inlet_water_m3, "inlet water volume")
        wo = finite(outlet_water_m3, "outlet water volume")
        if t <= self.time or wi < 0 or wo < 0:
            raise ValueError("time must increase and water volumes must be nonnegative")
        parts, complete = self._snapshot(positions)
        masses = [fsum(self.bodies[k].mass_kg * p[i] for k, p in parts.items()) for i in range(3)]
        delta_down = [self.bodies[k].mass_kg * (p[2] - self.parts[k][2]) for k, p in parts.items()]
        delta_up = [self.bodies[k].mass_kg * (p[0] - self.parts[k][0]) for k, p in parts.items()]
        out_step = fsum(max(0.0, v) for v in delta_down)
        return_step = fsum(max(0.0, -v) for v in delta_down)
        gross_out = fsum((self.gross_out, out_step))
        gross_return = fsum((self.gross_return, return_step))
        gross_up = fsum((self.gross_up, fsum(max(0.0, v) for v in delta_up)))
        gross_up_return = fsum((self.gross_up_return, fsum(max(0.0, -v) for v in delta_up)))
        water_in, water_out = fsum((self.water_in, wi)), fsum((self.water_out, wo))
        residuals = [abs(fsum(masses) - self.mass0) / self.mass0,
                     abs(fsum((gross_out, -gross_return, -masses[2]))) / self.mass0,
                     abs(fsum((gross_up, -gross_up_return, -masses[0]))) / self.mass0]
        pv = water_in / self.pore_volume
        ratio = out_step / wo if wo else None
        values = masses + [gross_out, gross_return, gross_up, gross_up_return, water_in, water_out, pv] + residuals
        if ratio is not None:
            values.append(ratio)
        if not all(isfinite(v) for v in values) or max(residuals) > TOL:
            raise ValueError("nonfinite or nonconservative ledger")
        new_events = sorted(complete - self.complete)
        result = {
            "time_s": t, "event_time_bracket_s": [self.time, t],
            "upstream_mass_kg": masses[0], "inside_mass_kg": masses[1], "downstream_mass_kg": masses[2],
            "net_downstream_fraction": masses[2] / self.mass0,
            "gross_outward_mass_kg": gross_out, "gross_return_mass_kg": gross_return,
            "outward_mass_this_step_kg": out_step, "return_mass_this_step_kg": return_step,
            "gross_upstream_mass_kg": gross_up, "gross_upstream_return_mass_kg": gross_up_return,
            "complete_exit_ids_this_step": new_events,
            "complete_exit_events": self.complete_events + len(new_events),
            "unique_ever_completely_exited": len(self.ever_complete | complete),
            "pore_volumes_flushed": pv,
            "diagnostic_outward_mass_per_collected_water_kg_m3": ratio,
            "maximum_relative_balance_residual": max(residuals),
        }
        # Commit only after every input and derived value passes.
        self.parts, self.time = parts, t
        self.water_in, self.water_out = water_in, water_out
        self.gross_out, self.gross_return = gross_out, gross_return
        self.gross_up, self.gross_up_return = gross_up, gross_up_return
        self.complete_events += len(new_events)
        self.complete = complete
        self.ever_complete |= complete
        return result
