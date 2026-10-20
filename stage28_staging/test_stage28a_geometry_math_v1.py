#!/usr/bin/env python3
"""Dependency-light unit checks for Stage28a periodic fibre geometry."""

from __future__ import annotations

import math
import unittest

import numpy as np

from stage28a_geometry_math_v1 import (
    periodic_segment_distance,
    segment_segment_distance,
    synchronous_distance_history,
)


class SegmentDistanceTests(unittest.TestCase):
    def test_parallel_segments(self):
        value = segment_segment_distance((0, 0, 0), (1, 0, 0), (0, 2, 0), (1, 2, 0))
        self.assertTrue(math.isclose(value, 2.0, abs_tol=1e-14))

    def test_crossing_segments(self):
        value = segment_segment_distance((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0))
        self.assertTrue(math.isclose(value, 0.0, abs_tol=1e-14))

    def test_endpoint_distance(self):
        value = segment_segment_distance((0, 0, 0), (1, 0, 0), (2, 1, 0), (2, 2, 0))
        self.assertTrue(math.isclose(value, math.sqrt(2.0), abs_tol=1e-14))

    def test_periodic_image(self):
        value = periodic_segment_distance(
            (0.05, 0.2, 0.2),
            (0.05, 0.8, 0.2),
            (0.95, 0.2, 0.2),
            (0.95, 0.8, 0.2),
            (1.0, 1.0, 1.0),
        )
        self.assertTrue(math.isclose(value, 0.1, abs_tol=1e-14))

    def test_synchronous_translation(self):
        first = {
            "rear_m": [0.0, 0.0, 0.0],
            "tip_m": [1.0, 0.0, 0.0],
            "pull_direction": [0.0, 1.0, 0.0],
        }
        second = {
            "rear_m": [0.0, 1.0, 0.0],
            "tip_m": [1.0, 1.0, 0.0],
            "pull_direction": [0.0, -1.0, 0.0],
        }
        values = synchronous_distance_history(first, second, (10, 10, 10), np.asarray([0, 0.25, 0.5]))
        np.testing.assert_allclose(values, [1.0, 0.5, 0.0], atol=1e-14, rtol=0.0)


if __name__ == "__main__":
    unittest.main()
