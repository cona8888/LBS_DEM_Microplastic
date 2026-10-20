"""Wall-compatible interpolation of an archived cell-centred voxel field.

Solid-cell velocities must be exactly zero.  Trilinear interpolation is then
performed across all eight native values.  This is bounded and continuous but
inherits the voxel wall-location error; it is not a sub-grid reconstruction.
"""
import numpy as np


class WallCellField:
    def __init__(self, velocity_xyz, spacing, fluid):
        self.u = np.asarray(velocity_xyz, float)
        self.fluid = np.asarray(fluid, bool)
        if self.u.ndim != 4 or self.u.shape[0] != 3:
            raise ValueError("velocity must have shape (3,nx,ny,nz)")
        self.shape = np.asarray(self.u.shape[1:])
        if self.fluid.shape != tuple(self.shape):
            raise ValueError("phase shape mismatch")
        if spacing <= 0 or not np.isfinite(self.u).all():
            raise ValueError("invalid field")
        if np.any(self.u[:, ~self.fluid] != 0):
            raise ValueError("solid-cell velocity must be exactly zero")
        self.dx = float(spacing)

    def sample(self, position):
        position = np.asarray(position, float)
        if position.shape != (3,) or not np.isfinite(position).all():
            raise ValueError("finite three-dimensional position required")
        coordinate = position / self.dx - 0.5
        lower = np.floor(coordinate).astype(int)
        weight = coordinate - lower
        velocity = np.zeros(3)
        gradient = np.zeros((3, 3))
        for bits in np.ndindex(2, 2, 2):
            bit = np.asarray(bits)
            index = tuple((lower + bit) % self.shape)
            factors = np.where(bit, weight, 1 - weight)
            value = self.u[(slice(None),) + index]
            velocity += np.prod(factors) * value
            for axis in range(3):
                other = np.delete(factors, axis)
                gradient[:, axis] += value * (1 if bit[axis] else -1) * np.prod(other) / self.dx
        if not np.isfinite(velocity).all() or not np.isfinite(gradient).all():
            raise FloatingPointError("nonfinite interpolation")
        return velocity, gradient
