"""Allocation-reduced evaluation of the unchanged Stage39 trilinear field.

The native eight-cell stencil, periodic indexing, solid-cell zero values,
summation order and gradient arithmetic are retained. No field values or wall
locations are changed. This is numerical equivalence, not near-wall validation.
"""
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "stage39_staging") not in sys.path:
    sys.path.insert(0, str(ROOT / "stage39_staging"))
from wall_field_v1 import WallCellField as ReferenceWallCellField

# np.ndindex order is fixed. Bytes-backed arrays cannot be made writeable.
_BITS = tuple(np.frombuffer(np.asarray(bits, dtype=np.int64).tobytes(), dtype=np.int64)
              for bits in np.ndindex(2, 2, 2))


class WallCellFieldExact(ReferenceWallCellField):
    """Drop-in field sampler using the original constructor and data arrays."""

    @classmethod
    def from_field(cls, field):
        if not isinstance(field, ReferenceWallCellField):
            raise TypeError("Stage39 WallCellField required")
        return cls(field.u, field.dx, field.fluid)

    def sample(self, position):
        position = np.asarray(position, float)
        if position.shape != (3,) or not np.isfinite(position).all():
            raise ValueError("finite three-dimensional position required")
        coordinate = position / self.dx - 0.5
        lower = np.floor(coordinate).astype(int)
        weight = coordinate - lower
        velocity = np.zeros(3)
        gradient = np.zeros((3, 3))
        for bit in _BITS:
            index = tuple((lower + bit) % self.shape)
            factors = np.where(bit, weight, 1 - weight)
            value = self.u[(slice(None),) + index]
            # Keep the original three-factor np.prod and stencil accumulation.
            velocity += np.prod(factors) * value
            # np.prod of the two remaining factors multiplies in this order.
            # Keep the original value * sign * product / dx operation order.
            gradient[:, 0] += value * (1 if bit[0] else -1) * (factors[1] * factors[2]) / self.dx
            gradient[:, 1] += value * (1 if bit[1] else -1) * (factors[0] * factors[2]) / self.dx
            gradient[:, 2] += value * (1 if bit[2] else -1) * (factors[0] * factors[1]) / self.dx
        if not np.isfinite(velocity).all() or not np.isfinite(gradient).all():
            raise FloatingPointError("nonfinite interpolation")
        return velocity, gradient


# Optional conventional name for explicit construction by existing loaders.
WallCellField = WallCellFieldExact
